let currentFile = null;
let currentType = 'image';

// DOM элементы
const imageInput = document.getElementById('imageInput');
const video2dInput = document.getElementById('video2dInput');
const video3dTopInput = document.getElementById('video3dTopInput');
const video3dSideInput = document.getElementById('video3dSideInput');

const imageUploadArea = document.getElementById('imageUploadArea');
const video2dUploadArea = document.getElementById('video2dUploadArea');
const video3dTopArea = document.getElementById('video3dTopArea');
const video3dSideArea = document.getElementById('video3dSideArea');

const resultArea = document.getElementById('resultArea');
const resultImage = document.getElementById('resultImage');
const resultVideo = document.getElementById('resultVideo');
const loadingOverlay = document.getElementById('loadingOverlay');
const closeResult = document.getElementById('closeResult');
const ballCount = document.getElementById('ballCount');
const confidence = document.getElementById('confidence');
const trajectoryInfo = document.getElementById('trajectoryInfo');
const process3dBtn = document.getElementById('process3dBtn');
const calibrateBtn = document.getElementById('calibrateBtn');

// Состояние для 3D
let video3dTopFile = null;
let video3dSideFile = null;

// Переключение табов
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        currentType = tab;

        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tab}-tab`).classList.add('active');

        resultArea.style.display = 'none';
    });
});

// Фото
imageUploadArea.addEventListener('click', () => imageInput.click());
setupDragDrop(imageUploadArea, imageInput, handleImageUpload, 'image');

// 2D Видео
video2dUploadArea.addEventListener('click', () => video2dInput.click());
setupDragDrop(video2dUploadArea, video2dInput, handleVideo2dUpload, 'video');

// 3D Видео - верхняя камера
video3dTopArea.addEventListener('click', () => video3dTopInput.click());
setupDragDrop(video3dTopArea, video3dTopInput, (file) => {
    video3dTopFile = file;
    video3dTopArea.style.borderColor = '#00d4ff';
    check3dReady();
}, 'video');

// 3D Видео - боковая камера
video3dSideArea.addEventListener('click', () => video3dSideInput.click());
setupDragDrop(video3dSideArea, video3dSideInput, (file) => {
    video3dSideFile = file;
    video3dSideArea.style.borderColor = '#00d4ff';
    check3dReady();
}, 'video');

function setupDragDrop(area, input, handler, type) {
    area.addEventListener('dragover', (e) => {
        e.preventDefault();
        area.style.borderColor = '#00d4ff';
    });
    area.addEventListener('dragleave', () => {
        area.style.borderColor = 'rgba(255, 255, 255, 0.2)';
    });
    area.addEventListener('drop', (e) => {
        e.preventDefault();
        area.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith(type + '/')) {
            handler(file);
            if (input) input.files = e.dataTransfer.files;
        }
    });
    input.addEventListener('change', (e) => {
        if (e.target.files[0]) handler(e.target.files[0]);
    });
}

function check3dReady() {
    if (video3dTopFile && video3dSideFile) {
        process3dBtn.disabled = false;
    } else {
        process3dBtn.disabled = true;
    }
}

// Обработка фото
async function handleImageUpload(file) {
    if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, выберите изображение');
        return;
    }

    loadingOverlay.style.display = 'flex';
    const formData = new FormData();
    formData.append('image', file);

    try {
        const statsResponse = await fetch('http://localhost:5000/api/detect/stream', {
            method: 'POST',
            body: formData
        });
        const statsData = await statsResponse.json();

        if (statsData.success) {
            ballCount.textContent = statsData.count;
            if (statsData.count > 0) {
                const avgConfidence = statsData.detections.reduce((sum, d) => sum + d.confidence, 0) / statsData.count;
                confidence.textContent = `${(avgConfidence * 100).toFixed(1)}%`;
            } else {
                confidence.textContent = '0%';
            }
        }

        const imageResponse = await fetch('http://localhost:5000/api/detect/image', {
            method: 'POST',
            body: formData
        });
        const blob = await imageResponse.blob();
        const url = URL.createObjectURL(blob);

        resultImage.src = url;
        resultImage.style.display = 'block';
        resultVideo.style.display = 'none';
        if (trajectoryInfo) trajectoryInfo.style.display = 'none';
        resultArea.style.display = 'block';
        resultImage.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при обработке изображения: ' + error.message);
    } finally {
        loadingOverlay.style.display = 'none';
    }
}

// Обработка 2D видео (с трекингом)
async function handleVideo2dUpload(file) {
    if (!file.type.startsWith('video/')) {
        alert('Пожалуйста, выберите видео');
        return;
    }

    loadingOverlay.style.display = 'flex';
    const formData = new FormData();
    formData.append('video', file);

    try {
        const response = await fetch('http://localhost:5000/api/track/2d', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);

            resultVideo.src = url;
            resultVideo.style.display = 'block';
            resultImage.style.display = 'none';

            ballCount.textContent = 'Треккинг';
            confidence.textContent = '2D траектория';

            if (trajectoryInfo) {
                trajectoryInfo.style.display = 'block';
                trajectoryInfo.innerHTML = '📈 Жёлтая линия — траектория движения мяча';
            }

            resultArea.style.display = 'block';
            resultVideo.scrollIntoView({ behavior: 'smooth' });
        } else {
            const error = await response.json();
            alert('Ошибка: ' + error.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при обработке видео: ' + error.message);
    } finally {
        loadingOverlay.style.display = 'none';
    }
}

// Обработка 3D видео (две камеры)
process3dBtn.addEventListener('click', async () => {
    if (!video3dTopFile || !video3dSideFile) {
        alert('Загрузите видео с обеих камер');
        return;
    }

    loadingOverlay.style.display = 'flex';
    const formData = new FormData();
    formData.append('video_top', video3dTopFile);
    formData.append('video_side', video3dSideFile);

    try {
        const response = await fetch('http://localhost:5000/api/track/3d', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            ballCount.textContent = data.points_3d || '3D';
            confidence.textContent = 'Траектория';

            if (trajectoryInfo) {
                trajectoryInfo.style.display = 'block';
                trajectoryInfo.innerHTML = `🎯 3D траектория построена!<br>
                📊 Точек: ${data.points_3d || 0}<br>
                📁 Файл: ${data.trajectory_file || 'сохранён'}`;
            }

            resultArea.style.display = 'block';
            alert(`3D трекинг завершен! Построено ${data.points_3d || 0} точек.`);
        } else {
            alert('Ошибка: ' + data.error);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при 3D обработке: ' + error.message);
    } finally {
        loadingOverlay.style.display = 'none';
    }
});

// Калибровка камер
calibrateBtn?.addEventListener('click', () => {
    showCalibrationModal();
});

function showCalibrationModal() {
    const modal = document.createElement('div');
    modal.className = 'calibration-modal';
    modal.innerHTML = `
        <div class="calibration-content">
            <h3>Калибровка камер</h3>
            <p style="color:#ccc; font-size:12px;">Отметьте 4 угла стола на изображении сверху</p>
            <input type="file" id="calibImageInput" accept="image/*">
            <div id="calibPoints" style="margin: 16px 0;">
                <p style="color:#888; font-size:12px;">После загрузки изображения кликните по 4 углам стола:</p>
                <p style="color:#00d4ff; font-size:11px;">1 - левый дальний | 2 - правый дальний | 3 - левый ближний | 4 - правый ближний</p>
            </div>
            <button id="saveCalibBtn" disabled>Сохранить калибровку</button>
            <button id="closeCalibBtn" style="margin-top:8px; background:rgba(255,255,255,0.1);">Закрыть</button>
        </div>
    `;
    document.body.appendChild(modal);

    let corners = [];
    const imgInput = modal.querySelector('#calibImageInput');
    const saveBtn = modal.querySelector('#saveCalibBtn');

    imgInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            const url = URL.createObjectURL(file);
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);

                let clickCount = 0;
                canvas.style.cursor = 'crosshair';
                canvas.addEventListener('click', (e) => {
                    const rect = canvas.getBoundingClientRect();
                    const scaleX = canvas.width / rect.width;
                    const scaleY = canvas.height / rect.height;
                    const x = (e.clientX - rect.left) * scaleX;
                    const y = (e.clientY - rect.top) * scaleY;

                    corners.push([x, y]);
                    ctx.beginPath();
                    ctx.arc(x, y, 5, 0, 2 * Math.PI);
                    ctx.fillStyle = '#00d4ff';
                    ctx.fill();
                    ctx.fillStyle = 'white';
                    ctx.font = '16px Arial';
                    ctx.fillText(clickCount + 1, x - 10, y - 10);

                    clickCount++;
                    if (clickCount === 4) {
                        saveBtn.disabled = false;
                    }
                });

                modal.querySelector('#calibPoints').appendChild(canvas);
            };
            img.src = url;
        }
    });

    saveBtn.addEventListener('click', async () => {
        if (corners.length === 4) {
            try {
                const response = await fetch('http://localhost:5000/api/calibrate/top', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ corners: corners })
                });
                const result = await response.json();
                if (result.success) {
                    alert('Калибровка сохранена!');
                    modal.remove();
                }
            } catch (error) {
                alert('Ошибка калибровки: ' + error.message);
            }
        }
    });

    modal.querySelector('#closeCalibBtn').addEventListener('click', () => modal.remove());
}

// Закрыть результат
closeResult.addEventListener('click', () => {
    resultArea.style.display = 'none';
    resultImage.src = '';
    resultVideo.src = '';
    if (trajectoryInfo) trajectoryInfo.style.display = 'none';
});

// Проверка соединения
async function checkServer() {
    try {
        const response = await fetch('http://localhost:5000/api/health');
        if (!response.ok) console.warn('Сервер не отвечает');
        else console.log('✅ Сервер подключён');
    } catch (error) {
        console.warn('Не удалось подключиться к серверу');
    }
}
checkServer();