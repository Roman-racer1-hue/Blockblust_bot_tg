import random
import copy

# Библиотека фигур (нельзя поворачивать или отражать!)
SHAPES_LIBRARY = [
    # Одиночные
    [[1]],
    
    # Пары
    [[1, 1]],           # горизонтальная пара
    [[1], [1]],         # вертикальная пара
    
    # Тройки
    [[1, 1, 1]],        # горизонтальная тройка
    [[1], [1], [1]],    # вертикальная тройка
    
    # Квадраты
    [[1, 1], 
     [1, 1]],
    
    # L-образные (фиксированные)
    [[1, 0], 
     [1, 1]],
    
    [[1, 1], 
     [0, 1]],
    
    [[1, 1], 
     [1, 0]],
    
    [[0, 1], 
     [1, 1]],
    
    # Маленькие формы
    [[1, 1, 0], 
     [0, 1, 1]],
    
    [[0, 1, 1], 
     [1, 1, 0]],
]

def generate_trio(current_grid):
    """
    Генерирует тройку фигур с учетом текущего состояния поля
    """
    # Анализируем поле
    empty_cells = sum(row.count(0) for row in current_grid)
    center_density = calculate_center_density(current_grid)
    
    # Выбираем фигуры с учетом сложности
    trio = []
    for _ in range(3):
        shape = select_shape_based_on_difficulty(empty_cells, center_density)
        trio.append(shape)
    
    return trio

def calculate_center_density(grid):
    """
    Рассчитывает заполненность центра поля (4x4 в центре 8x8)
    """
    if not grid or len(grid) < 8:
        return 0
    
    center_cells = 0
    total_center = 0
    
    for y in range(2, 6):  # Центральные 4 строки
        for x in range(2, 6):  # Центральные 4 столбца
            total_center += 1
            if grid[y][x] == 1:
                center_cells += 1
    
    return center_cells / total_center if total_center > 0 else 0

def select_shape_based_on_difficulty(empty_cells, center_density):
    """
    Выбирает фигуру на основе сложности игры
    """
    # Веса для разных типов фигур
    weights = []
    
    for shape in SHAPES_LIBRARY:
        weight = 1.0
        shape_size = sum(sum(row) for row in shape)
        
        # Учитываем размер фигуры и свободное место
        if empty_cells < 20:  # Мало свободного места
            if shape_size > 2:
                weight *= 0.3  # Большие фигуры реже
            else:
                weight *= 1.5  # Маленькие фигуры чаще
        
        # Учитываем заполненность центра
        if center_density > 0.7:  # Центр заполнен
            if shape_size > 1:
                weight *= 0.5  # Большие фигуры сложнее разместить
        
        # Балансировка: не давать слишком много одинаковых фигур
        weights.append(weight)
    
    # Нормализуем веса
    total_weight = sum(weights)
    if total_weight > 0:
        weights = [w / total_weight for w in weights]
    
    # Выбираем случайную фигуру с учетом весов
    return random.choices(SHAPES_LIBRARY, weights=weights, k=1)[0]

def can_place_shape(grid, shape, x, y):
    """
    Проверяет можно ли разместить фигуру в позиции (x, y)
    """
    if not grid or not shape:
        return False
    
    grid_height = len(grid)
    grid_width = len(grid[0]) if grid_height > 0 else 0
    
    shape_height = len(shape)
    shape_width = len(shape[0]) if shape_height > 0 else 0
    
    # Проверка границ
    if (x < 0 or x + shape_width > grid_width or 
        y < 0 or y + shape_height > grid_height):
        return False
    
    # Проверка что все клетки фигуры попадают на пустые клетки
    for row_idx, row in enumerate(shape):
        for col_idx, cell in enumerate(row):
            if cell == 1:  # Часть фигуры
                if grid[y + row_idx][x + col_idx] != 0:
                    return False
    
    return True

def place_shape(grid, shape, x, y):
    """
    Размещает фигуру на поле и возвращает новое состояние поля
    """
    if not can_place_shape(grid, shape, x, y):
        return None
    
    # Создаем копию поля
    new_grid = copy.deepcopy(grid)
    
    # Размещаем фигуру
    for row_idx, row in enumerate(shape):
        for col_idx, cell in enumerate(row):
            if cell == 1:
                new_grid[y + row_idx][x + col_idx] = 1
    
    return new_grid

def check_lines_after_placement(grid):
    """
    Проверяет и удаляет заполненные линии после размещения фигуры
    Возвращает количество очищенных линий
    """
    lines_cleared = 0
    grid_height = len(grid)
    grid_width = len(grid[0]) if grid_height > 0 else 0
    
    # Проверка горизонтальных линий
    horizontal_to_clear = []
    for y in range(grid_height):
        if all(cell == 1 for cell in grid[y]):
            horizontal_to_clear.append(y)
            lines_cleared += 1
    
    # Проверка вертикальных линий
    vertical_to_clear = []
    for x in range(grid_width):
        column_full = True
        for y in range(grid_height):
            if grid[y][x] != 1:
                column_full = False
                break
        
        if column_full:
            vertical_to_clear.append(x)
            lines_cleared += 1
    
    # Очищаем линии
    for y in horizontal_to_clear:
        for x in range(grid_width):
            grid[y][x] = 0
    
    for x in vertical_to_clear:
        for y in range(grid_height):
            grid[y][x] = 0
    
    return lines_cleared

def calculate_score(blocks_placed, lines_cleared, combo_multiplier):
    """
    Рассчитывает очки за ход
    """
    base_score = blocks_placed * 10
    lines_score = lines_cleared * 100
    combo_bonus = lines_score * (combo_multiplier - 1) if combo_multiplier > 1 else 0
    
    return base_score + lines_score + combo_bonus

def check_game_over(grid, available_shapes):
    """
    Проверяет Game Over условие
    Возвращает True если нельзя разместить хотя бы одну из доступных фигур
    """
    grid_height = len(grid)
    grid_width = len(grid[0]) if grid_height > 0 else 0
    
    for shape in available_shapes:
        shape_height = len(shape)
        shape_width = len(shape[0]) if shape_height > 0 else 0
        
        # Пробуем все возможные позиции
        for y in range(grid_height - shape_height + 1):
            for x in range(grid_width - shape_width + 1):
                if can_place_shape(grid, shape, x, y):
                    return False  # Нашли возможное размещение
    
    return True  # Нельзя разместить ни одну фигуру

def find_best_placement(grid, shape):
    """
    Находит лучшую позицию для размещения фигуры
    (позицию которая даст максимальное количество линий)
    """
    best_score = -1
    best_position = None
    
    grid_height = len(grid)
    grid_width = len(grid[0]) if grid_height > 0 else 0
    shape_height = len(shape)
    shape_width = len(shape[0]) if shape_height > 0 else 0
    
    for y in range(grid_height - shape_height + 1):
        for x in range(grid_width - shape_width + 1):
            if can_place_shape(grid, shape, x, y):
                # Симулируем размещение
                temp_grid = copy.deepcopy(grid)
                for row_idx, row in enumerate(shape):
                    for col_idx, cell in enumerate(row):
                        if cell == 1:
                            temp_grid[y + row_idx][x + col_idx] = 1
                
                # Проверяем сколько линий очистится
                lines_cleared = check_lines_after_placement(temp_grid)
                
                if lines_cleared > best_score:
                    best_score = lines_cleared
                    best_position = (x, y)
    
    return best_position, best_score
