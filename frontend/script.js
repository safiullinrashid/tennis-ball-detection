let currentFile = null;
let currentType = 'image';

// DOM элементы
const imageInput = document.getElementById('imageInput');
const videoInput = document.getElementById('videoInput');
const imageUploadArea = document.getElementById('imageUploadArea');
const videoUploadArea = document.getElementById('videoUploadArea');
const resultArea = document.getElementById('resultArea');
const resultImage = document.getElementById('resultImage');
const resultVideo = document.getElementById('resultVideo');
const loadingOverlay = document.getElementById('loadingOverlay');
const closeResult = document.getElementById('closeResult');
const ballCount = document.getElementById('ballCount');
const confidence = document.getElementById('confidence');

// Переключение табов
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tab = btn.dataset.tab;
        currentType = tab;

        // Обновляем активную кнопку
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Показываем нужный контент
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${tab}-tab`).classList.add('active');

        // Скрываем результат
        resultArea.style.display = 'none';
    });
});

// Upload area handlers
imageUploadArea.addEventListener('click', () => imageInput.click());
videoUploadArea.addEventListener('click', () => videoInput.click());

// Drag and drop для фото
imageUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    imageUploadArea.style.borderColor = '#00d4ff';
});

imageUploadArea.addEventListener('dragleave', () => {
    imageUploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
});

imageUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    imageUploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
        handleImageUpload(file);
    }
});

// Drag and drop для видео
videoUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    videoUploadArea.style.borderColor = '#00d4ff';
});

videoUploadArea.addEventListener('dragleave', () => {
    videoUploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
});

videoUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    videoUploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
        handleVideoUpload(file);
    }
});

// Обработка выбора файла
imageInput.addEventListener('change', (e) => {
    if (e.target.files[0]) {
        handleImageUpload(e.target.files[0]);
    }
});

videoInput.addEventListener('change', (e) => {
    if (e.target.files[0]) {
        handleVideoUpload(e.target.files[0]);
    }
});

// Обработка фото
async function handleImageUpload(file) {
    if (!file.type.startsWith('image/')) {
        alert('Пожалуйста, выберите изображение');
        return;
    }

    currentFile = file;
    loadingOverlay.style.display = 'flex';

    const formData = new FormData();
    formData.append('image', file);

    try {
        // Получаем детекции для статистики
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

        // Получаем обработанное изображение
        const imageResponse = await fetch('http://localhost:5000/api/detect/image', {
            method: 'POST',
            body: formData
        });

        const blob = await imageResponse.blob();
        const url = URL.createObjectURL(blob);

        resultImage.src = url;
        resultImage.style.display = 'block';
        resultVideo.style.display = 'none';

        resultArea.style.display = 'block';
        resultImage.scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка при обработке изображения: ' + error.message);
    } finally {
        loadingOverlay.style.display = 'none';
    }
}

// Обработка видео
async function handleVideoUpload(file) {
    if (!file.type.startsWith('video/')) {
        alert('Пожалуйста, выберите видео');
        return;
    }

    if (file.size > 100 * 1024 * 1024) {
        alert('Видео слишком большое (макс. 100MB)');
        return;
    }

    currentFile = file;
    loadingOverlay.style.display = 'flex';

    const formData = new FormData();
    formData.append('video', file);

    try {
        const response = await fetch('http://localhost:5000/api/detect/video', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);

            resultVideo.src = url;
            resultVideo.style.display = 'block';
            resultImage.style.display = 'none';

            ballCount.textContent = 'Обработано';
            confidence.textContent = 'Готово';

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

// Закрыть результат
closeResult.addEventListener('click', () => {
    resultArea.style.display = 'none';
    resultImage.src = '';
    resultVideo.src = '';
});

// Проверка соединения с сервером
async function checkServer() {
    try {
        const response = await fetch('http://localhost:5000/api/health');
        if (!response.ok) {
            console.warn('Сервер не отвечает');
        }
    } catch (error) {
        console.warn('Не удалось подключиться к серверу');
    }
}

checkServer();