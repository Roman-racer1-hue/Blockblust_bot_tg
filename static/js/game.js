// Инициализация Telegram Web App
let tg = window.Telegram.WebApp;
let user = null;

// Игровые переменные
let game = {
    grid: null,
    currentTrio: [],
    selectedShape: null,
    selectedShapeIndex: -1,
    score: 0,
    combo: 1,
    level: 1,
    blocksPlaced: 0,
    linesCleared: 0,
    maxCombo: 1,
    gameState: 'menu', // menu, playing, paused, gameOver
    startTime: null,
    gameDuration: 0,
    timerInterval: null
};

// Цвета для фигур
const SHAPE_COLORS = [
    '#2196F3', // синий
    '#4CAF50', // зеленый
    '#FF9800', // оранжевый
    '#E91E63', // розовый
    '#9C27B0', // фиолетовый
    '#00BCD4', // голубой
    '#FFC107', // желтый
    '#795548'  // коричневый
];

// Инициализация игры
function initGame() {
    // Инициализация сетки 8x8
    game.grid = Array(8).fill().map(() => Array(8).fill(0));
    
    // Создаем клетки сетки
    const gridElement = document.getElementById('game-grid');
    gridElement.innerHTML = '';
    
    for (let y = 0; y < 8; y++) {
        for (let x = 0; x < 8; x++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.x = x;
            cell.dataset.y = y;
            cell.addEventListener('click', () => handleCellClick(x, y));
            gridElement.appendChild(cell);
        }
    }
    
    // Загружаем статистику пользователя
    loadUserStats();
    
    // Инициализируем Telegram Web App
    tg.expand();
    tg.BackButton.hide();
    
    // Получаем данные пользователя из Telegram
    user = tg.initDataUnsafe?.user;
    if (user) {
        console.log('Telegram user:', user);
    }
}

// Загрузка статистики пользователя
async function loadUserStats() {
    if (!user) return;
    
    try {
        const response = await fetch(`/api/get_user_stats?telegram_id=${user.id}`);
        const data = await response.json();
        
        if (data.success && data.stats) {
            document.getElementById('best-score').textContent = data.stats.best_score;
            document.getElementById('total-games').textContent = data.stats.total_games;
        }
    } catch (error) {
        console.error('Error loading user stats:', error);
    }
}

// Начать новую игру
function startNewGame() {
    game.grid = Array(8).fill().map(() => Array(8).fill(0));
    game.score = 0;
    game.combo = 1;
    game.level = 1;
    game.blocksPlaced = 0;
    game.linesCleared = 0;
    game.maxCombo = 1;
    game.gameState = 'playing';
    game.startTime = Date.now();
    
    // Обновляем UI
    updateScore();
    updateCombo();
    updateLevel();
    
    // Генерируем первую тройку фигур
    generateNewTrio();
    
    // Обновляем сетку
    updateGrid();
    
    // Переключаем на игровой экран
    document.getElementById('game-menu').style.display = 'none';
    document.getElementById('game-over').style.display = 'none';
    document.querySelector('.game-board').style.display = 'block';
    
    // Показываем кнопку "Продолжить" в меню
    document.getElementById('continue-btn').style.display = 'block';
    
    // Запускаем таймер
    if (game.timerInterval) clearInterval(game.timerInterval);
    game.timerInterval = setInterval(() => {
        game.gameDuration = Math.floor((Date.now() - game.startTime) / 1000);
    }, 1000);
}

// Генерация новой тройки фигур
async function generateNewTrio() {
    try {
        const response = await fetch('/api/generate_trio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ grid: game.grid })
        });
        
        const data = await response.json();
        
        if (data.success) {
            game.currentTrio = data.trio;
            renderShapes();
            checkGameOver();
        } else {
            showNotification('Ошибка генерации фигур', 'error');
        }
    } catch (error) {
        console.error('Error generating trio:', error);
        showNotification('Ошибка соединения', 'error');
    }
}

// Отображение фигур на панели
function renderShapes() {
    for (let i = 0; i < 3; i++) {
        const shapeSlot = document.getElementById(`shape-${i}`);
        const shapePreview = shapeSlot.querySelector('.shape-preview');
        
        // Очищаем превью
        shapePreview.innerHTML = '';
        shapePreview.style.gridTemplateColumns = `repeat(${game.currentTrio[i]?.[0]?.length || 1}, 1fr)`;
        shapePreview.style.gridTemplateRows = `repeat(${game.currentTrio[i]?.length || 1}, 1fr)`;
        
        // Заполняем превью
        if (game.currentTrio[i]) {
            const shape = game.currentTrio[i];
            for (let y = 0; y < shape.length; y++) {
                for (let x = 0; x < shape[y].length; x++) {
                    if (shape[y][x] === 1) {
                        const block = document.createElement('div');
                        block.style.background = SHAPE_COLORS[i];
                        block.style.borderRadius = '3px';
                        shapePreview.appendChild(block);
                    }
                }
            }
        }
        
        // Добавляем обработчик клика
        shapeSlot.onclick = () => selectShape(i);
    }
}

// Выбор фигуры
function selectShape(index) {
    if (game.gameState !== 'playing') return;
    
    // Снимаем выделение с предыдущей фигуры
    if (game.selectedShapeIndex !== -1) {
        document.getElementById(`shape-${game.selectedShapeIndex}`).classList.remove('selected');
    }
    
    // Выделяем новую фигуру
    game.selectedShapeIndex = index;
    game.selectedShape = game.currentTrio[index];
    document.getElementById(`shape-${index}`).classList.add('selected');
    
    // Подсвечиваем доступные клетки
    highlightAvailableCells();
}

// Подсветка доступных клеток для размещения
function highlightAvailableCells() {
    if (!game.selectedShape) return;
    
    // Снимаем подсветку со всех клеток
    document.querySelectorAll('.cell').forEach(cell => {
        cell.classList.remove('highlight');
    });
    
    const shape = game.selectedShape;
    const shapeHeight = shape.length;
    const shapeWidth = shape[0].length;
    
    // Проверяем все возможные позиции
    for (let y = 0; y <= 8 - shapeHeight; y++) {
        for (let x = 0; x <= 8 - shapeWidth; x++) {
            if (canPlaceShape(shape, x, y)) {
                // Подсвечиваем клетки, которые займет фигура
                for (let sy = 0; sy < shapeHeight; sy++) {
                    for (let sx = 0; sx < shapeWidth; sx++) {
                        if (shape[sy][sx] === 1) {
                            const cell = document.querySelector(`.cell[data-x="${x + sx}"][data-y="${y + sy}"]`);
                            if (cell) {
                                cell.classList.add('highlight');
                            }
                        }
                    }
                }
            }
        }
    }
}

// Проверка можно ли разместить фигуру
function canPlaceShape(shape, x, y) {
    const shapeHeight = shape.length;
    const shapeWidth = shape[0].length;
    
    // Проверка границ
    if (x < 0 || x + shapeWidth > 8 || y < 0 || y + shapeHeight > 8) {
        return false;
    }
    
    // Проверка что все клетки фигуры попадают на пустые клетки
    for (let sy = 0; sy < shapeHeight; sy++) {
        for (let sx = 0; sx < shapeWidth; sx++) {
            if (shape[sy][sx] === 1 && game.grid[y + sy][x + sx] !== 0) {
                return false;
            }
        }
    }
    
    return true;
}

// Обработчик клика по клетке
async function handleCellClick(x, y) {
    if (game.gameState !== 'playing' || !game.selectedShape) return;
    
    // Проверяем можно ли разместить фигуру
    const canPlace = await checkPlacement(game.selectedShape, x, y);
    
    if (canPlace) {
        // Размещаем фигуру
        placeShape(game.selectedShape, x, y);
        
        // Удаляем использованную фигуру из тройки
        game.currentTrio.splice(game.selectedShapeIndex, 1);
        
        // Сбрасываем выбор
        game.selectedShape = null;
        game.selectedShapeIndex = -1;
        document.querySelectorAll('.shape-slot').forEach(slot => slot.classList.remove('selected'));
        
        // Если все фигуры размещены - генерируем новые
        if (game.currentTrio.length === 0) {
            setTimeout(() => {
                generateNewTrio();
                updateGrid();
            }, 500);
        } else {
            // Обновляем отображение фигур
            renderShapes();
            updateGrid();
        }
        
        // Снимаем подсветку
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('highlight');
        });
    } else {
        showNotification('Невозможно разместить фигуру здесь!', 'warning');
    }
}

// Проверка размещения на сервере
async function checkPlacement(shape, x, y) {
    try {
        const response = await fetch('/api/check_placement', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                grid: game.grid,
                shape: shape,
                x: x,
                y: y
            })
        });
        
        const data = await response.json();
        return data.success && data.can_place;
    } catch (error) {
        console.error('Error checking placement:', error);
        return false;
    }
}

// Размещение фигуры на поле
function placeShape(shape, x, y) {
    // Размещаем фигуру на сетке
    for (let sy = 0; sy < shape.length; sy++) {
        for (let sx = 0; sx < shape[sy].length; sx++) {
            if (shape[sy][sx] === 1) {
                game.grid[y + sy][x + sx] = 1;
                game.blocksPlaced++;
            }
        }
    }
    
    // Проверяем линии
    const linesCleared = checkLines();
    
    // Обновляем счет
    if (linesCleared > 0) {
        // Увеличиваем комбо
        game.combo++;
        if (game.combo > game.maxCombo) {
            game.maxCombo = game.combo;
        }
        
        // Обновляем комбо в UI
        updateCombo();
        
        // Показываем эффект комбо
        showComboEffect(linesCleared);
    } else {
        // Сбрасываем комбо
        game.combo = 1;
        updateCombo();
    }
    
    // Добавляем очки
    const shapeBlocks = shape.flat().filter(cell => cell === 1).length;
    const baseScore = shapeBlocks * 10;
    const linesScore = linesCleared * 100;
    const comboBonus = linesScore * (game.combo - 1);
    
    game.score += baseScore + linesScore + comboBonus;
    game.linesCleared += linesCleared;
    
    // Обновляем UI
    updateScore();
    
    // Проверяем повышение уровня
    const newLevel = Math.floor(game.score / 1000) + 1;
    if (newLevel > game.level) {
        game.level = newLevel;
        updateLevel();
        showNotification(`Уровень ${game.level}!`, 'success');
    }
    
    // Обновляем сетку
    updateGrid();
    
    // Визуальные эффекты
    showPlacementEffect(x, y, shape);
}

// Проверка и удаление заполненных линий
function checkLines() {
    let linesCleared = 0;
    
    // Проверка горизонтальных линий
    const horizontalToClear = [];
    for (let y = 0; y < 8; y++) {
        if (game.grid[y].every(cell => cell === 1)) {
            horizontalToClear.push(y);
            linesCleared++;
        }
    }
    
    // Проверка вертикальных линий
    const verticalToClear = [];
    for (let x = 0; x < 8; x++) {
        let columnFull = true;
        for (let y = 0; y < 8; y++) {
            if (game.grid[y][x] !== 1) {
                columnFull = false;
                break;
            }
        }
        
        if (columnFull) {
            verticalToClear.push(x);
            linesCleared++;
        }
    }
    
    // Очищаем линии
    for (const y of horizontalToClear) {
        for (let x = 0; x < 8; x++) {
            game.grid[y][x] = 0;
        }
    }
    
    for (const x of verticalToClear) {
        for (let y = 0; y < 8; y++) {
            game.grid[y][x] = 0;
        }
    }
    
    // Анимация очистки линий
    if (linesCleared > 0) {
        animateLineClear(horizontalToClear, verticalToClear);
    }
    
    return linesCleared;
}

// Анимация очистки линий
function animateLineClear(horizontalLines, verticalLines) {
    // Анимация горизонтальных линий
    horizontalLines.forEach(y => {
        for (let x = 0; x < 8; x++) {
            const cell = document.querySelector(`.cell[data-x="${x}"][data-y="${y}"]`);
            if (cell) {
                cell.style.animation = 'none';
                setTimeout(() => {
                    cell.style.animation = 'clearAnimation 0.5s ease';
                }, 10);
            }
        }
    });
    
    // Анимация вертикальных линий
    verticalLines.forEach(x => {
        for (let y = 0; y < 8; y++) {
            const cell = document.querySelector(`.cell[data-x="${x}"][data-y="${y}"]`);
            if (cell) {
                cell.style.animation = 'none';
                setTimeout(() => {
                    cell.style.animation = 'clearAnimation 0.5s ease';
                }, 10);
            }
        }
    });
    
    // Добавляем CSS анимацию
    if (!document.getElementById('clearAnimationStyle')) {
        const style = document.createElement('style');
        style.id = 'clearAnimationStyle';
        style.textContent = `
            @keyframes clearAnimation {
                0% { transform: scale(1); opacity: 1; }
                50% { transform: scale(1.2); opacity: 0.7; }
                100% { transform: scale(0); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
}

// Визуальный эффект размещения
function showPlacementEffect(x, y, shape) {
    const centerX = x + shape[0].length / 2;
    const centerY = y + shape.length / 2;
    
    // Создаем эффект частиц
    for (let i = 0; i < 10; i++) {
        setTimeout(() => {
            const particle = document.createElement('div');
            particle.style.position = 'absolute';
            particle.style.left = `${centerX * 50 + 25}px`; // 50px размер клетки
            particle.style.top = `${centerY * 50 + 25}px`;
            particle.style.width = '10px';
            particle.style.height = '10px';
            particle.style.background = SHAPE_COLORS[game.selectedShapeIndex] || '#2196F3';
            particle.style.borderRadius = '50%';
            particle.style.pointerEvents = 'none';
            particle.style.zIndex = '1000';
            
            document.querySelector('.grid-container').appendChild(particle);
            
            // Анимация частицы
            const angle = Math.random() * Math.PI * 2;
            const distance = 20 + Math.random() * 30;
            const targetX = Math.cos(angle) * distance;
            const targetY = Math.sin(angle) * distance;
            
            particle.animate([
                { transform: 'translate(0, 0) scale(1)', opacity: 1 },
                { transform: `translate(${targetX}px, ${targetY}px) scale(0)`, opacity: 0 }
            ], {
                duration: 500,
                easing: 'ease-out'
            }).onfinish = () => particle.remove();
        }, i * 50);
    }
}

// Эффект комбо
function showComboEffect(linesCleared) {
    const comboText = document.createElement('div');
    comboText.textContent = `COMBO x${game.combo}!`;
    comboText.style.position = 'absolute';
    comboText.style.top = '50%';
    comboText.style.left = '50%';
    comboText.style.transform = 'translate(-50%, -50%)';
    comboText.style.fontSize = '48px';
    comboText.style.fontWeight = 'bold';
    comboText.style.color = '#FF9800';
    comboText.style.textShadow = '0 0 20px rgba(255, 152, 0, 0.7)';
    comboText.style.pointerEvents = 'none';
    comboText.style.zIndex = '1000';
    comboText.style.animation = 'comboAnimation 1s ease-out';
    
    document.querySelector('.grid-container').appendChild(comboText);
    
    // Добавляем CSS анимацию
    if (!document.getElementById('comboAnimationStyle')) {
        const style = document.createElement('style');
        style.id = 'comboAnimationStyle';
        style.textContent = `
            @keyframes comboAnimation {
                0% { transform: translate(-50%, -50%) scale(0.5); opacity: 0; }
                50% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; }
                100% { transform: translate(-50%, -50%) scale(1); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }
    
    // Удаляем текст после анимации
    setTimeout(() => comboText.remove(), 1000);
}

// Обновление сетки
function updateGrid() {
    document.querySelectorAll('.cell').forEach(cell => {
        const x = parseInt(cell.dataset.x);
        const y = parseInt(cell.dataset.y);
        
        if (game.grid[y][x] === 1) {
            cell.classList.add('filled');
            cell.classList.remove('highlight');
        } else {
            cell.classList.remove('filled');
        }
    });
}

// Обновление счета
function updateScore() {
    document.getElementById('score').textContent = game.score;
}

// Обновление комбо
function updateCombo() {
    document.getElementById('combo').textContent = `x${game.combo}`;
}

// Обновление уровня
function updateLevel() {
    document.getElementById('level').textContent = game.level;
}

// Проверка Game Over
function checkGameOver() {
    // Проверяем можно ли разместить хотя бы одну фигуру из тройки
    let canPlaceAny = false;
    
    for (const shape of game.currentTrio) {
        const shapeHeight = shape.length;
        const shapeWidth = shape[0].length;
        
        for (let y = 0; y <= 8 - shapeHeight; y++) {
            for (let x = 0; x <= 8 - shapeWidth; x++) {
                if (canPlaceShape(shape, x, y)) {
                    canPlaceAny = true;
                    break;
                }
            }
            if (canPlaceAny) break;
        }
        if (canPlaceAny) break;
    }
    
    if (!canPlaceAny) {
        endGame();
    }
}

// Завершение игры
async function endGame() {
    game.gameState = 'gameOver';
    
    if (game.timerInterval) {
        clearInterval(game.timerInterval);
        game.timerInterval = null;
    }
    
    // Показываем экран Game Over
    document.getElementById('final-score').textContent = game.score;
    document.getElementById('final-lines').textContent = game.linesCleared;
    document.getElementById('final-combo').textContent = `x${game.maxCombo}`;
    
    // Проверяем новый рекорд
    const bestScore = parseInt(document.getElementById('best-score').textContent);
    if (game.score > bestScore) {
        document.getElementById('new-record').style.display = 'block';
    }
    
    document.querySelector('.game-board').style.display = 'none';
    document.getElementById('game-over').style.display = 'flex';
    
    // Сохраняем результат на сервере
    await saveGameResult();
}

// Сохранение результата игры
async function saveGameResult() {
    if (!user) return;
    
    try {
        const response = await fetch('/api/save_score', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                telegram_id: user.id,
                score: game.score,
                lines_cleared: game.linesCleared,
                blocks_placed: game.blocksPlaced,
                max_combo: game.maxCombo,
                duration: game.gameDuration
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Обновляем статистику
            document.getElementById('best-score').textContent = data.stats.best_score;
            document.getElementById('total-games').textContent = data.stats.total_games;
            
            if (data.is_new_best) {
                showNotification('Новый рекорд! 🏆', 'success');
            }
        }
    } catch (error) {
        console.error('Error saving game result:', error);
    }
}

// Показать уведомление
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// Загрузка топа игроков
async function loadLeaderboard(period = 'all') {
    try {
        const response = await fetch(`/api/get_leaderboard?period=${period}`);
        const data = await response.json();
        
        if (data.success) {
            const content = document.getElementById('leaderboard-content');
            content.innerHTML = '';
            
            if (data.leaderboard.length === 0) {
                content.innerHTML = '<p style="text-align: center; color: #aaa;">Нет данных</p>';
                return;
            }
            
            data.leaderboard.forEach((player, index) => {
                const item = document.createElement('div');
                item.className = 'leaderboard-item';
                item.innerHTML = `
                    <div class="leaderboard-rank">${index + 1}</div>
                    <div class="leaderboard-name">${player.name}</div>
                    <div class="leaderboard-score">${player.score}</div>
                `;
                content.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Error loading leaderboard:', error);
    }
}

// Загрузка достижений
async function loadAchievements() {
    if (!user) return;
    
    try {
        const response = await fetch(`/api/get_achievements?telegram_id=${user.id}`);
        const data = await response.json();
        
        if (data.success) {
            const content = document.getElementById('achievements-content');
            content.innerHTML = '';
            
            if (data.achievements.length === 0) {
                content.innerHTML = '<p style="text-align: center; color: #aaa;">Достижений пока нет</p>';
                return;
            }
            
            data.achievements.forEach(achievement => {
                const item = document.createElement('div');
                item.className = 'achievement-item';
                item.innerHTML = `
                    <div class="achievement-icon">🏅</div>
                    <div class="achievement-details">
                        <div class="achievement-name">${achievement.name}</div>
                        <div class="achievement-description">${achievement.description}</div>
                        <div class="achievement-date">Получено: ${new Date(achievement.unlocked_at).toLocaleDateString('ru-RU')}</div>
                    </div>
                `;
                content.appendChild(item);
            });
        }
    } catch (error) {
        console.error('Error loading achievements:', error);
    }
}

// Обработчики событий
document.addEventListener('DOMContentLoaded', () => {
    initGame();
    
    // Кнопки меню
    document.getElementById('start-game-btn').addEventListener('click', startNewGame);
    document.getElementById('continue-btn').addEventListener('click', () => {
        document.getElementById('game-menu').style.display = 'none';
        document.querySelector('.game-board').style.display = 'block';
    });
    
    document.getElementById('stats-btn').addEventListener('click', () => {
        document.getElementById('stats-modal').style.display = 'flex';
        loadUserStats();
    });
    
    document.getElementById('leaderboard-btn').addEventListener('click', () => {
        document.getElementById('leaderboard-modal').style.display = 'flex';
        loadLeaderboard('all');
    });
    
    document.getElementById('achievements-btn').addEventListener('click', () => {
        document.getElementById('achievements-modal').style.display = 'flex';
        loadAchievements();
    });
    
    document.getElementById('help-btn').addEventListener('click', () => {
        document.getElementById('help-modal').style.display = 'flex';
    });
    
    // Кнопки игры
    document.getElementById('new-game-btn').addEventListener('click', startNewGame);
    document.getElementById('hint-btn').addEventListener('click', showHint);
    document.getElementById('play-again-btn').addEventListener('click', startNewGame);
    document.getElementById('back-to-menu-btn').addEventListener('click', () => {
        document.getElementById('game-over').style.display = 'none';
        document.getElementById('game-menu').style.display = 'flex';
    });
    
    // Закрытие модальных окон
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            btn.closest('.modal').style.display = 'none';
        });
    });
    
    // Клик вне модального окна
    window.addEventListener('click', (event) => {
        document.querySelectorAll('.modal').forEach(modal => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    });
    
    // Переключение вкладок в лидерборде
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Убираем активный класс со всех кнопок
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            // Добавляем активный класс текущей кнопке
            btn.classList.add('active');
            // Загружаем данные для выбранного периода
            loadLeaderboard(btn.dataset.period);
        });
    });
});

// Подсказка
function showHint() {
    if (!game.selectedShape || game.gameState !== 'playing') return;
    
    // Находим лучшую позицию для текущей фигуры
    let bestScore = -1;
    let bestPosition = null;
    
    const shape = game.selectedShape;
    const shapeHeight = shape.length;
    const shapeWidth = shape[0].length;
    
    for (let y = 0; y <= 8 - shapeHeight; y++) {
        for (let x = 0; x <= 8 - shapeWidth; x++) {
            if (canPlaceShape(shape, x, y)) {
                // Симулируем размещение
                const tempGrid = JSON.parse(JSON.stringify(game.grid));
                for (let sy = 0; sy < shapeHeight; sy++) {
                    for (let sx = 0; sx < shapeWidth; sx++) {
                        if (shape[sy][sx] === 1) {
                            tempGrid[y + sy][x + sx] = 1;
                        }
                    }
                }
                
                // Проверяем сколько линий очистится
                const linesCleared = simulateLineCheck(tempGrid);
                
                if (linesCleared > bestScore) {
                    bestScore = linesCleared;
                    bestPosition = { x, y };
                }
            }
        }
    }
    
    if (bestPosition) {
        // Подсвечиваем лучшую позицию
        document.querySelectorAll('.cell').forEach(cell => {
            cell.classList.remove('highlight');
        });
        
        for (let sy = 0; sy < shapeHeight; sy++) {
            for (let sx = 0; sx < shapeWidth; sx++) {
                if (shape[sy][sx] === 1) {
                    const cell = document.querySelector(`.cell[data-x="${bestPosition.x + sx}"][data-y="${bestPosition.y + sy}"]`);
                    if (cell) {
                        cell.classList.add('highlight');
                        cell.style.animation = 'hintPulse 1s infinite';
                    }
                }
            }
        }
        
        // Добавляем CSS анимацию
        if (!document.getElementById('hintAnimationStyle')) {
            const style = document.createElement('style');
            style.id = 'hintAnimationStyle';
            style.textContent = `
                @keyframes hintPulse {
                    0% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0.7); }
                    70% { box-shadow: 0 0 0 10px rgba(76, 175, 80, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(76, 175, 80, 0); }
                }
            `;
            document.head.appendChild(style);
        }
        
        showNotification('Лучшая позиция подсвечена!', 'info');
    } else {
        showNotification('Нет доступных позиций для этой фигуры', 'warning');
    }
}

// Симуляция проверки линий
function simulateLineCheck(grid) {
    let linesCleared = 0;
    
    // Проверка горизонтальных линий
    for (let y = 0; y < 8; y++) {
        if (grid[y].every(cell => cell === 1)) {
            linesCleared++;
        }
    }
    
    // Проверка вертикальных линий
    for (let x = 0; x < 8; x++) {
        let columnFull = true;
        for (let y = 0; y < 8; y++) {
            if (grid[y][x] !== 1) {
                columnFull = false;
                break;
            }
        }
        
        if (columnFull) {
            linesCleared++;
        }
    }
    
    return linesCleared;
}

// Обработка ошибок
window.addEventListener('error', function(event) {
    console.error('Game error:', event.error);
    showNotification('Произошла ошибка в игре', 'error');
});
