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

function setFileLoaded(el, file, label) {
    el.innerHTML = `
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" style="color: #00d4ff;">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/>
        </svg>
        <p style="color: #00d4ff; font-weight: 600;">${file.name}</p>
        <small>${(file.size / 1024 / 1024).toFixed(1)} MB — нажмите для замены</small>
    `;
    el.style.borderColor = '#00d4ff';
    el.style.borderStyle = 'solid';
    el.dataset.fileLoaded = 'true';
}

// 3D Видео - верхняя камера
video3dTopArea.addEventListener('click', () => video3dTopInput.click());
setupDragDrop(video3dTopArea, video3dTopInput, (file) => {
    video3dTopFile = file;
    setFileLoaded(video3dTopArea, file, 'СВЕРХУ');
    check3dReady();
}, 'video');

// 3D Видео - боковая камера
video3dSideArea.addEventListener('click', () => video3dSideInput.click());
setupDragDrop(video3dSideArea, video3dSideInput, (file) => {
    video3dSideFile = file;
    setFileLoaded(video3dSideArea, file, 'СБОКУ');
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

// Обработка 2D видео
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
            const contentType = response.headers.get('content-type') || '';
            if (contentType.includes('video/mp4')) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                const a = document.createElement('a');
                a.href = url;
                a.download = `tracked_2d_${file.name}`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);

                resultImage.style.display = 'none';
                document.getElementById('viewer3d').style.display = 'none';
                document.getElementById('tracks3d_container').style.display = 'none';
                document.getElementById('tracks2d_container').style.display = 'none';

                resultVideo.src = url;
                resultVideo.style.display = 'block';
                resultVideo.load();
                resultVideo.play().catch(() => {});

                resultArea.style.display = 'block';
                ballCount.textContent = '2D';
                confidence.textContent = 'Траектория';
                if (trajectoryInfo) {
                    trajectoryInfo.style.display = 'block';
                    trajectoryInfo.innerHTML = '📥 Видео скачано<br>🟢 Зелёные рамки — детекция мяча<br>🟡 Жёлтая линия — траектория';
                }
                resultVideo.scrollIntoView({ behavior: 'smooth' });
            } else {
                const data = await response.json();
                if (data.success && data.video_ok === false) {
                    // JSON fallback — видео не создалось, рисуем через canvas
                    alert('Видео не удалось создать — будет показана траектория на кадрах (без видеофайла)');
                    resultImage.style.display = 'none';
                    document.getElementById('viewer3d').style.display = 'none';
                    document.getElementById('tracks3d_container').style.display = 'none';
                    resultArea.style.display = 'block';
                    ballCount.textContent = data.detections || 0;
                    confidence.textContent = '2D траектория';
                    document.getElementById('tracks2d_container').innerHTML = '';

                    const trajDiv = document.createElement('div');
                    trajDiv.style.cssText = 'flex: 1; background: rgba(0,0,0,0.3); border-radius: 12px; padding: 8px; text-align: center;';
                    trajDiv.innerHTML = '<div style="color: #ffcc00; font-size: 11px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 1px;">Траектория мяча</div>';
                    const trajCanvas = document.createElement('canvas');
                    trajCanvas.width = 320; trajCanvas.height = 240;
                    trajCanvas.style.cssText = 'width: 100%; height: 180px; border-radius: 8px; background: #0a0a1a;';
                    trajDiv.appendChild(trajCanvas);
                    document.getElementById('tracks2d_container').appendChild(trajDiv);
                    document.getElementById('tracks2d_container').style.display = 'flex';
                    draw2dTrackOnCanvas(trajCanvas, data.trajectory || [], '#ffcc00');
                } else {
                    alert('Ошибка сервера: ' + (data.error || 'неизвестная ошибка'));
                }
            }
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

// 3D сцена
let scene3d, camera3d, renderer3d, controls3d;
let ballMesh, trajectoryLine, trailDots;
let points3d = [];
let animFrame = 0;
let isPlaying = false;
let animId = null;
let overlayAnimId2d = null;
let anim3dTop = null;

// Обработка 3D видео (две камеры)
process3dBtn.addEventListener('click', async () => {
    if (typeof THREE === 'undefined') {
        alert('3D вьювер недоступен: не удалось загрузить Three.js (проверьте интернет)');
        return;
    }
    if (!video3dTopFile || !video3dSideFile) {
        alert('Загрузите видео с обеих камер');
        return;
    }

    loadingOverlay.style.display = 'flex';
    const formData = new FormData();
    formData.append('video_top', video3dTopFile);
    formData.append('video_side', video3dSideFile);
    formData.append('render_video', document.getElementById('renderVideoCheck').checked ? '1' : '0');

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 900000);
        const response = await fetch('http://localhost:5000/api/track/3d', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const data = await response.json();

        if (data.success) {
            points3d = data.trajectory || [];

            ballCount.textContent = points3d.length;
            confidence.textContent = '3D траектория';

            resultImage.style.display = 'none';
            resultVideo.style.display = 'none';
            document.getElementById('viewer3d').style.display = 'block';
            resultArea.style.display = 'block';

            initScene3d(points3d);

            document.getElementById('tracks2d_container').style.display = 'none';
            const t3c = document.getElementById('tracks3d_container');
            t3c.innerHTML = '';
            t3c.style.display = 'flex';
            t3c.style.flexDirection = 'column';
            t3c.style.gap = '12px';

            const baseUrl = 'http://localhost:5000';

            async function autoDownload(url, filename) {
                if (!url) return;
                try {
                    const r = await fetch(baseUrl + url);
                    const blob = await r.blob();
                    const u = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = u;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                } catch(e) {
                    console.warn('Не удалось скачать', filename, e);
                }
            }

            // Автоскачивание видео
            autoDownload(data.top_video_url, 'tracked_top.mp4');
            setTimeout(() => autoDownload(data.side_video_url, 'tracked_side.mp4'), 500);

            // Траектории — показываем inline + скачиваем
            if (data.top_traj_url || data.side_traj_url) {
                const row = document.createElement('div');
                row.style.cssText = 'display: flex; gap: 12px; width: 100%; flex-wrap: wrap;';

                function makeImgCard(url, label, color) {
                    if (!url) return null;
                    const div = document.createElement('div');
                    div.style.cssText = 'flex: 1; min-width: 200px; background: rgba(0,0,0,0.3); border-radius: 12px; padding: 8px; text-align: center;';
                    div.innerHTML = `<div style="color: ${color}; font-size: 11px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 1px;">${label}</div>`;
                    const img = document.createElement('img');
                    img.src = baseUrl + url;
                    img.style.cssText = 'width: 100%; border-radius: 8px; display: block; cursor: pointer;';
                    img.onclick = () => autoDownload(url, label.toLowerCase().replace(' ', '_') + '.png');
                    div.appendChild(img);
                    return div;
                }

                const t1 = makeImgCard(data.top_traj_url, 'Траектория сверху', '#00d4ff');
                const t2 = makeImgCard(data.side_traj_url, 'Траектория сбоку', '#ff8800');
                if (t1) row.appendChild(t1);
                if (t2) row.appendChild(t2);
                t3c.appendChild(row);

                // Скачиваем траектории
                setTimeout(() => autoDownload(data.top_traj_url, 'trajectory_top.png'), 1000);
                setTimeout(() => autoDownload(data.side_traj_url, 'trajectory_side.png'), 1500);
            }

            const info = document.createElement('div');
            info.style.cssText = 'color: #888; font-size: 12px; text-align: center; width: 100%; padding: 8px;';
            info.textContent = `3D точек: ${data.points_3d} | Совпадений камер: ${data.top_2d ? data.top_2d.length : 0}`;
            t3c.appendChild(info);

            if (trajectoryInfo) trajectoryInfo.style.display = 'none';
            resultVideo.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert('Ошибка сервера: ' + (data.error || 'неизвестная ошибка'));
        }
    } catch (error) {
        console.error('Error:', error);
        if (error.name === 'AbortError') {
            alert('3D обработка не завершилась за 15 минут. Слишком длинное видео.');
        } else {
            alert('Ошибка соединения: ' + error.message + '\nПроверьте, запущен ли сервер (http://localhost:5000)');
        }
    } finally {
        loadingOverlay.style.display = 'none';
    }
});

function initScene3d(points) {
    const container = document.getElementById('viewer3d');
    const w = container.clientWidth;
    const h = container.clientHeight;

    if (renderer3d) {
        if (animId) cancelAnimationFrame(animId);
        renderer3d.dispose();
        container.innerHTML = `<div id="controls3d" style="position: absolute; bottom: 12px; left: 50%; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; background: rgba(0,0,0,0.6); padding: 8px 16px; border-radius: 8px; z-index: 10;">
            <button id="playBtn3d" style="background: none; border: none; color: #fff; cursor: pointer; font-size: 18px;">▶</button>
            <input type="range" id="scrubber3d" min="0" max="1" step="0.001" style="width: 200px; accent-color: #00d4ff;">
            <span id="frameInfo3d" style="color: #aaa; font-size: 12px; min-width: 60px;">0/0</span>
            <span style="color:#888;font-size:11px;">скорость</span>
            <input type="range" id="speed3d" min="1" max="20" value="15" step="1" style="width:80px;accent-color:#ff8800;" oninput="document.getElementById('speedVal3d').textContent=this.value">
            <span id="speedVal3d" style="color:#ff8800;font-size:12px;min-width:18px;">15</span>
            <button id="fullscreenBtn3d" style="background: none; border: none; color: #fff; cursor: pointer; font-size: 16px;">⛶</button>
        </div>`;
        renderer3d = null;
    }

    scene3d = new THREE.Scene();
    scene3d.background = new THREE.Color(0x1a1a2e);

    camera3d = new THREE.PerspectiveCamera(45, w / h, 1, 2000);
    camera3d.position.set(300, 250, 400);
    camera3d.lookAt(137, 0, 76);

    renderer3d = new THREE.WebGLRenderer({ antialias: true });
    renderer3d.setSize(w, h);
    renderer3d.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer3d.shadowMap.enabled = true;
    container.prepend(renderer3d.domElement);

    controls3d = new THREE.OrbitControls(camera3d, renderer3d.domElement);
    controls3d.target.set(137, 0, 76);
    controls3d.update();

    // Свет
    const ambient = new THREE.AmbientLight(0x404060, 0.6);
    scene3d.add(ambient);
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(200, 300, 100);
    scene3d.add(dirLight);
    const fillLight = new THREE.DirectionalLight(0x4488ff, 0.4);
    fillLight.position.set(-100, 100, -100);
    scene3d.add(fillLight);

    // Стол
    const tableGeo = new THREE.BoxGeometry(274, 2, 152.5);
    const tableMat = new THREE.MeshStandardMaterial({ color: 0x1a5276, roughness: 0.7 });
    const table = new THREE.Mesh(tableGeo, tableMat);
    table.position.set(137, -1, 76);
    table.receiveShadow = true;
    scene3d.add(table);

    // Разметка стола (линии)
    const lineMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.3 });
    // Белая линия посередине (ширина стола)
    const midPoints = [new THREE.Vector3(137, 0, 0), new THREE.Vector3(137, 0, 152.5)];
    const midGeo = new THREE.BufferGeometry().setFromPoints(midPoints);
    scene3d.add(new THREE.Line(midGeo, lineMat));

    // Рамка стола
    const framePts = [
        [0, 0], [274, 0], [274, 152.5], [0, 152.5], [0, 0]
    ].map(p => new THREE.Vector3(p[0], 0, p[1]));
    const frameGeo = new THREE.BufferGeometry().setFromPoints(framePts);
    scene3d.add(new THREE.Line(frameGeo, lineMat));

    // Ножки стола
    const legMat = new THREE.MeshStandardMaterial({ color: 0x333333 });
    for (const [x, z] of [[5, 5], [269, 5], [5, 147.5], [269, 147.5]]) {
        const leg = new THREE.Mesh(new THREE.BoxGeometry(3, 76, 3), legMat);
        leg.position.set(x, -76 / 2, z);
        scene3d.add(leg);
    }

    // Сетка
    const netMat = new THREE.MeshStandardMaterial({
        color: 0xcccccc,
        transparent: true,
        opacity: 0.4,
        wireframe: false,
        side: THREE.DoubleSide
    });
    const netGeo = new THREE.BoxGeometry(0.5, 15.25, 152.5);
    const net = new THREE.Mesh(netGeo, netMat);
    net.position.set(137, 15.25 / 2, 76);
    scene3d.add(net);

    // Вертикальные линии сетки
    const netLineMat = new THREE.LineBasicMaterial({ color: 0x888888, transparent: true, opacity: 0.2 });
    for (let i = 0; i <= 10; i++) {
        const z = (i / 10) * 152.5;
        const pts = [new THREE.Vector3(137, 0, z), new THREE.Vector3(137, 15.25, z)];
        const g = new THREE.BufferGeometry().setFromPoints(pts);
        scene3d.add(new THREE.Line(g, netLineMat));
    }

    // Траектория — полная, показываем только хвост через setDrawRange
    if (points.length > 1) {
        const pts = points.map(p => new THREE.Vector3(p.X, p.Z - 76, 152.5 - p.Y));
        const trajGeo = new THREE.BufferGeometry().setFromPoints(pts);
        trajGeo.setDrawRange(0, 1);
        const trajMat = new THREE.LineBasicMaterial({ color: 0xffaa00, linewidth: 2 });
        trajectoryLine = new THREE.Line(trajGeo, trajMat);
        scene3d.add(trajectoryLine);
    }

    // Точки траектории — хвост
    if (points.length > 0) {
        const dotGeo = new THREE.BufferGeometry();
        const positions = points.map(p => [p.X, p.Z - 76, 152.5 - p.Y]).flat();
        dotGeo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        dotGeo.setDrawRange(0, 1);
        const dotMat = new THREE.PointsMaterial({
            color: 0xffaa00,
            size: 3,
            sizeAttenuation: true
        });
        trailDots = new THREE.Points(dotGeo, dotMat);
        scene3d.add(trailDots);
    }

    // Мяч
    const ballGeo = new THREE.SphereGeometry(3.5, 16, 16);
    const ballMat = new THREE.MeshStandardMaterial({ color: 0xff8800, emissive: 0xff4400, emissiveIntensity: 0.4 });
    ballMesh = new THREE.Mesh(ballGeo, ballMat);
    if (points.length > 0) {
        ballMesh.position.set(points[0].X, points[0].Z - 76 + 4, 152.5 - points[0].Y);
    }
    scene3d.add(ballMesh);

    // Пол
    const floorGeo = new THREE.PlaneGeometry(600, 400);
    const floorMat = new THREE.MeshStandardMaterial({
        color: 0x111122,
        roughness: 0.9,
        transparent: true,
        opacity: 0.5,
        side: THREE.DoubleSide
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(137, -76, 76);
    scene3d.add(floor);

    // Управление
    animFrame = 0;
    isPlaying = false;
    const playBtn = document.getElementById('playBtn3d');
    const scrubber = document.getElementById('scrubber3d');
    const frameInfo = document.getElementById('frameInfo3d');

    scrubber.max = Math.max(0, points.length - 1);
    scrubber.value = 0;
    frameInfo.textContent = `0/${points.length}`;

    playBtn.onclick = () => {
        isPlaying = !isPlaying;
        playBtn.textContent = isPlaying ? '⏸' : '▶';
        if (isPlaying && animFrame >= points.length - 1) animFrame = 0;
        speedCounter = 0;
    };

    document.getElementById('fullscreenBtn3d').onclick = () => {
        if (!document.fullscreenElement) {
            container.requestFullscreen();
        } else {
            document.exitFullscreen();
        }
    };

    document.addEventListener('fullscreenchange', () => {
        if (document.fullscreenElement === container) {
            container.style.height = '100vh';
            container.style.width = '100vw';
            container.style.borderRadius = '0';
        } else {
            container.style.height = '480px';
            container.style.width = '100%';
            container.style.borderRadius = '12px';
        }
        const cw = container.clientWidth;
        const ch = container.clientHeight;
        camera3d.aspect = cw / ch;
        camera3d.updateProjectionMatrix();
        renderer3d.setSize(cw, ch);
    });

    scrubber.oninput = () => {
        animFrame = parseInt(scrubber.value);
        updateBallPosition(animFrame);
        if (isPlaying) {
            isPlaying = false;
            playBtn.textContent = '▶';
        }
    };

    window.addEventListener('resize', () => {
        const cw = container.clientWidth;
        const ch = container.clientHeight;
        camera3d.aspect = cw / ch;
        camera3d.updateProjectionMatrix();
        renderer3d.setSize(cw, ch);
    });

    // Запускаем рендер-цикл
    let speedCounter = 0;
    function renderLoop() {
        if (!renderer3d || !scene3d || !camera3d) return;
        if (isPlaying) {
            speedCounter++;
            const speedEl = document.getElementById('speed3d');
            const val = speedEl ? parseInt(speedEl.value) : 10;
            const step = 21 - val;
            if (speedCounter % step === 0 && animFrame < points.length - 1) {
                animFrame++;
                updateBallPosition(animFrame);
            }
            if (animFrame >= points.length - 1) {
                isPlaying = false;
                document.getElementById('playBtn3d').textContent = '▶';
            }
        }
        controls3d.update();
        renderer3d.render(scene3d, camera3d);
        animId = requestAnimationFrame(renderLoop);
    }
    renderLoop();
}

function updateBallPosition(idx) {
    if (!ballMesh || points3d.length === 0) return;
    idx = Math.min(idx, points3d.length - 1);
    const p = points3d[idx];
    ballMesh.position.set(p.X, p.Z - 76, 152.5 - p.Y);
    document.getElementById('scrubber3d').value = idx;
    document.getElementById('frameInfo3d').textContent = `${idx + 1}/${points3d.length}`;

    const tailSize = 30;
    const start = Math.max(0, idx - tailSize);
    const count = idx - start + 1;
    if (trajectoryLine) trajectoryLine.geometry.setDrawRange(start, count);
    if (trailDots) trailDots.geometry.setDrawRange(start, count);
}

function draw2dTrackOnCanvas(canvas, points, color) {
    if (!canvas || points.length < 2) return;
    // Сортируем по frame (если есть)
    const sorted = points.sort((a, b) => (a.frame || 0) - (b.frame || 0));
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    const xs = sorted.map(p => p.x);
    const ys = sorted.map(p => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const rangeX = Math.max(maxX - minX, 1);
    const rangeY = Math.max(maxY - minY, 1);
    const pad = 20;

    function normX(v) { return pad + (v - minX) / rangeX * (w - pad * 2); }
    function normY(v) { return pad + (v - minY) / rangeY * (h - pad * 2); }

    ctx.clearRect(0, 0, w, h);

    // Сетка
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
        const x = pad + i / 5 * (w - pad * 2);
        const y = pad + i / 5 * (h - pad * 2);
        ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, h - pad); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(w - pad, y); ctx.stroke();
    }

    // Линия траектории
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < sorted.length; i++) {
        const x = normX(sorted[i].x);
        const y = normY(sorted[i].y);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Точки
    for (let i = 0; i < sorted.length; i++) {
        const x = normX(sorted[i].x);
        const y = normY(sorted[i].y);
        const alpha = (i + 1) / sorted.length;
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.3 + alpha * 0.7;
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Первая и последняя точки
    const first = points[0];
    ctx.fillStyle = '#00ff88';
    ctx.beginPath();
    ctx.arc(normX(first.x), normY(first.y), 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = '9px sans-serif';
    ctx.fillText('Старт', normX(first.x) + 6, normY(first.y) + 3);

    const last = points[points.length - 1];
    ctx.fillStyle = '#ff4444';
    ctx.beginPath();
    ctx.arc(normX(last.x), normY(last.y), 5, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.fillText('Финиш', normX(last.x) + 6, normY(last.y) + 3);
}


// Закрыть результат
closeResult.addEventListener('click', () => {
    resultArea.style.display = 'none';
    resultImage.src = '';
    resultVideo.src = '';
    document.getElementById('viewer3d').style.display = 'none';
    document.getElementById('tracks2d_container').style.display = 'none';
    document.getElementById('tracks3d_container').style.display = 'none';
    if (trajectoryInfo) trajectoryInfo.style.display = 'none';
    if (animId) cancelAnimationFrame(animId);
    isPlaying = false;
    if (anim3dTop) cancelAnimationFrame(anim3dTop);
    anim3dTop = null;
    if (overlayAnimId2d) cancelAnimationFrame(overlayAnimId2d);
    overlayAnimId2d = null;
    if (renderer3d) {
        renderer3d.dispose();
        renderer3d = null;
    }
    // Очищаем blob URL-ы
    document.querySelectorAll('#tracks2d_container video, #tracks3d_container video').forEach(v => {
        if (v.src) URL.revokeObjectURL(v.src);
    });
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