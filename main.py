import os
import sys
import csv
import pygame

pygame.init()
pygame.display.set_caption("Tower Defence Example")


# -----------------------------------------------------------------------------------
# ------------------------ ФУНКЦИЯ ЗАГРУЗКИ ИЗОБРАЖЕНИЙ -----------------------------
# -----------------------------------------------------------------------------------
def load_image(name, colorkey=None):
    """
    Загружает изображение из папки data.
    Если colorkey задан, устанавливает прозрачность.
    """
    fullname = os.path.join('data', name)
    if not os.path.isfile(fullname):
        print(f"Файл с изображением '{fullname}' не найден")
        sys.exit()
    image = pygame.image.load(fullname)
    if colorkey is not None:
        image = image.convert()
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
        image.set_colorkey(colorkey)
    else:
        image = image.convert_alpha()
    return image


# -----------------------------------------------------------------------------------
# ------------------------ КОНСТАНТЫ И НАСТРОЙКИ -------------------------------------
# -----------------------------------------------------------------------------------
WIDTH = 800
HEIGHT = 600
FPS = 50

# Координаты, где будет стоять башня (примерно центр)
TOWER_POS = (400, 300)

# Цвета
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GREEN = (50, 200, 50)
RED = (255, 50, 50)
GRAY = (100, 100, 100)

# Стоимость размещения препятствия и оружия
BARRIER_COST = 20
WEAPON_COST = 30

# Сколько денег у игрока в начале
START_MONEY = 180

# Размер ячейки (для «сеточного» размещения)
CELL_SIZE = 40


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС КНОПКИ ----------------------------------------------
# -----------------------------------------------------------------------------------
class Button:
    """
    Простой класс кнопки для отрисовки в стартовом/финальном окне.
    """

    def __init__(self, rect, text, color=(150, 150, 150), text_color=BLACK, font_size=30):
        self.rect = pygame.Rect(rect)
        self.color = color
        self.text = text
        self.text_color = text_color
        self.font_size = font_size
        self.font = pygame.font.SysFont("arial", self.font_size)

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_surface = self.font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)

    def is_clicked(self, event_pos):
        return self.rect.collidepoint(event_pos)


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС ДЛЯ ТАБЛИЦЫ РЕЗУЛЬТАТОВ (CSV) -----------------------
# -----------------------------------------------------------------------------------
class ScoreTable:
    """
    Класс для хранения и загрузки результатов в CSV.
    Файл results.csv создаётся автоматически, если его нет.
    """

    def __init__(self, filename="results.csv"):
        self.filename = filename
        # создадим файл, если его нет
        if not os.path.exists(self.filename):
            with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Имя", "Очки"])

    def add_record(self, name, score):
        """
        Добавить новую запись об игроке
        """
        with open(self.filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([name, score])

    def get_best_scores(self, top_n=5):
        """
        Получить top_n лучших результатов (сортировка по убыванию очков)
        """
        scores = []
        with open(self.filename, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # пропустить заголовок
            for row in reader:
                if len(row) == 2:
                    n, s = row
                    scores.append((n, int(s)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС БАШНИ -----------------------------------------------
# -----------------------------------------------------------------------------------
class Tower(pygame.sprite.Sprite):
    """
    Башня, которую нужно защитить.
    """

    def __init__(self, pos, health=320):
        super().__init__()
        self.image = load_image("tower.png")
        self.rect = self.image.get_rect(topleft=pos)
        self.health = health  # здоровье башни

    def take_damage(self, amount):
        self.health -= amount
        if self.health < 0:
            self.health = 0


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС БАЗОВЫЙ ДЛЯ МОНСТРОВ --------------------------------
# -----------------------------------------------------------------------------------
class Monster(pygame.sprite.Sprite):
    """
    Базовый класс для всех монстров.
    Определяет базовое поведение движения, атаки и анимации.
    """

    def __init__(self, images_list, x, y, speed=2, damage=10, health=100):
        super().__init__()
        # images_list должен содержать список загруженных кадров анимации
        self.images = images_list
        self.current_frame = 0
        self.animation_speed = 0.15  # скорость переключения кадров
        self.image = self.images[int(self.current_frame)]
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

        self.speed = speed
        self.damage = damage
        self.health = health
        self.attack_delay = 60  # сколько тиков ждать между ударами
        self.attack_timer = 0

        # Состояние монстра: "move", "attack", "dead"
        self.state = "move"
        self.target = None

    def update(self, tower, barriers_group):
        """
        Обновляет позицию монстра и состояние анимации.
        """
        if self.state == "move":
            self.move_logic(tower, barriers_group)
        elif self.state == "attack":
            self.attack_logic()
        self.animate()

    def move_logic(self, tower, barriers_group):
        """
        Логика движения: монстр двигается к башне,
        если на пути нет барьера. Если встречает барьер – атакует барьер.
        """
        # Проверим, не сталкиваемся ли мы с барьером
        for barrier in barriers_group:
            if self.rect.colliderect(barrier.rect):
                self.state = "attack"
                self.target = barrier
                return

        # Двигаемся к башне
        if self.rect.x < tower.rect.x:
            self.rect.x += self.speed
        elif self.rect.x > tower.rect.x:
            self.rect.x -= self.speed

        if self.rect.y < tower.rect.y:
            self.rect.y += self.speed
        elif self.rect.y > tower.rect.y:
            self.rect.y -= self.speed

        # Если мы близко к башне, переходим к атаке
        if self.rect.colliderect(tower.rect):
            self.state = "attack"
            self.target = tower

    def attack_logic(self):
        """
        Логика атаки цели, будь то барьер или башня.
        """
        if self.target is not None:
            if hasattr(self.target, "health") and self.target.health <= 0:
                # Цель уничтожена, переходим обратно к движению
                self.state = "move"
                self.target = None
                return

            # Если мы ещё не готовы ударить (таймер не обнулён), то ждём
            if self.attack_timer > 0:
                self.attack_timer -= 1
            else:
                # Наносим урон
                self.target.take_damage(self.damage)
                self.attack_timer = self.attack_delay
        else:
            # Если цели нет, переходим к движению
            self.state = "move"

    def animate(self):
        """
        Простая анимация, переключающая кадры
        """
        self.current_frame += self.animation_speed
        if self.current_frame >= len(self.images):
            self.current_frame = 0
        self.image = self.images[int(self.current_frame)]

    def take_damage(self, amount):
        """
        Получить урон
        """
        self.health -= amount
        if self.health <= 0:
            self.state = "dead"
            self.kill()


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС ДЛЯ Гоблина (Наследует Monster) ---------------------
# -----------------------------------------------------------------------------------
class Goblin(Monster):
    """
    Гоблин — быстрый монстр с относительно небольшим уроном и здоровьем.
    """

    def __init__(self, x, y):
        images_list = [
            load_image("monster_goblin_1.png"),
            load_image("monster_goblin_2.png"),
            load_image("monster_goblin_3.png"),
        ]
        super().__init__(images_list, x, y, speed=3, damage=5, health=50)


# ------------------------ КЛАСС ДЛЯ Орка ------------------------
class Orc(Monster):
    """
    Орк — медлительный, но с большим уроном и здоровьем.
    """

    def __init__(self, x, y):
        images_list = [
            load_image("monster_orc_1.png"),
            load_image("monster_orc_2.png"),
            load_image("monster_orc_3.png"),
        ]
        super().__init__(images_list, x, y, speed=1, damage=20, health=150)


class Golem(Monster):
    """
    Голем — очень медленный, но с большим уроном и высоким здоровьем.
    """
    def __init__(self, x, y):
        images_list = [
            load_image("monster_golem_1.png"),
            load_image("monster_golem_2.png"),
            load_image("monster_golem_3.png"),
        ]
        # speed=1 (самый медленный), damage=30, health=200 (усиленные характеристики)
        super().__init__(images_list, x, y, speed=1, damage=30, health=200)


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС ПРЕПЯТСТВИЯ (баррикады) -----------------------------
# -----------------------------------------------------------------------------------
class Barrier(pygame.sprite.Sprite):
    """
    Препятствие, которое монстры должны сломать.
    """

    def __init__(self, x, y, health=100):
        super().__init__()
        self.image = load_image("barrier.png")
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)
        self.health = health

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.kill()


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС ОРУЖИЯ (устанавливаемого) ---------------------------
# -----------------------------------------------------------------------------------
class Weapon(pygame.sprite.Sprite):
    """
    Оружие, которое можно установить на поле. Оно стреляет в ближайшего монстра.
    """

    def __init__(self, x, y):
        super().__init__()
        self.image = load_image("weapon.png")
        self.rect = self.image.get_rect()
        self.rect.topleft = (x, y)
        self.fire_delay = 60  # задержка между выстрелами
        self.fire_timer = 0

    def update(self, monsters_group, bullets_group):
        # Уменьшаем таймер
        if self.fire_timer > 0:
            self.fire_timer -= 1
        else:
            # Найдём ближайшего монстра, чтобы выстрелить
            target = None
            min_dist = 999999
            for monster in monsters_group:
                dist = (monster.rect.centerx - self.rect.centerx) ** 2 + (monster.rect.centery - self.rect.centery) ** 2
                if dist < min_dist:
                    min_dist = dist
                    target = monster
            # Если нашли монстра в зоне поражения (условно не ограничиваем радиус)
            if target:
                # Стреляем
                bullet = Bullet(self.rect.centerx, self.rect.centery, target)
                bullets_group.add(bullet)
                self.fire_timer = self.fire_delay


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС ПУЛИ -----------------------------------------------
# -----------------------------------------------------------------------------------
class Bullet(pygame.sprite.Sprite):
    """
    Пуля, летит к выбранному монстру, нанося ему урон при попадании.
    """

    def __init__(self, x, y, target, speed=5, damage=10):
        super().__init__()
        self.image = load_image("bullet.png")
        self.rect = self.image.get_rect(center=(x, y))
        self.target = target
        self.speed = speed
        self.damage = damage

    def update(self):
        if not self.target.alive() or self.target.state == "dead":
            # Если цель уже мертва, удаляем пулю
            self.kill()
            return

        # Движемся к цели
        dx = self.target.rect.centerx - self.rect.centerx
        dy = self.target.rect.centery - self.rect.centery
        dist = (dx ** 2 + dy ** 2) ** 0.5

        if dist < self.speed:
            # Считаем, что попали
            self.target.take_damage(self.damage)
            self.kill()
        else:
            # Двигаемся по направлению к цели
            self.rect.x += self.speed * dx / dist
            self.rect.y += self.speed * dy / dist


# -----------------------------------------------------------------------------------
# ------------------------ КЛАСС УРОВНЯ (WAVES) --------------------------------------
# -----------------------------------------------------------------------------------
class GameLevel:
    """
    Класс описывает один уровень (его волны монстров и др.).
    """

    def __init__(self, waves):
        """
        waves: список кортежей (monster_class, количество, задержка_между_монстрами)
        Например:
        [(Goblin, 5, 60), (Orc, 2, 120)]
        """
        self.waves = waves
        self.current_wave_index = 0
        self.monsters_to_spawn = self.waves[self.current_wave_index][1]  # сколько монстров осталось выпустить
        self.spawn_delay = self.waves[self.current_wave_index][2]
        self.spawn_timer = 0
        self.monster_class = self.waves[self.current_wave_index][0]
        self.done = False  # флаг завершения уровня

    def update(self, monsters_group):
        """
        Запуск волны монстров с заданной периодичностью.
        """
        if self.done:
            return

        if self.spawn_timer > 0:
            self.spawn_timer -= 1
        else:
            # Спавним монстра
            x_spawn, y_spawn = 50, 50  # место спавна (можно менять/рандомизировать)
            monster = self.monster_class(x_spawn, y_spawn)
            monsters_group.add(monster)
            self.monsters_to_spawn -= 1
            self.spawn_timer = self.spawn_delay

            # Если в текущей волне все монстры выпущены
            if self.monsters_to_spawn <= 0:
                # Переходим к следующей волне
                self.current_wave_index += 1
                if self.current_wave_index >= len(self.waves):
                    # Все волны закончились
                    self.done = True
                else:
                    self.monsters_to_spawn = self.waves[self.current_wave_index][1]
                    self.spawn_delay = self.waves[self.current_wave_index][2]
                    self.spawn_timer = 0
                    self.monster_class = self.waves[self.current_wave_index][0]


# -----------------------------------------------------------------------------------
# ------------------------ ОСНОВНОЙ КЛАСС ИГРЫ ---------------------------------------
# -----------------------------------------------------------------------------------
class TowerDefenceGame:
    """
    Основной класс игры:
    - содержит циклы стартового экрана,
    - игрового процесса (по уровням),
    - финального экрана
    """

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True

        # Загружаем «тайл» земли (424x119).
        self.ground_tile = load_image("grounds.png")

        # Инициализируем таблицу рекордов
        self.score_table = ScoreTable()

        # Игровые переменные
        self.levels = [
            GameLevel([(Goblin, 5, 60), (Orc, 2, 120)]),
            GameLevel([(Goblin, 10, 30), (Orc, 3, 90)]),
            GameLevel([(Goblin, 5, 100), (Golem, 1, 50)])
        ]
        self.current_level_index = 0
        self.monsters = pygame.sprite.Group()
        self.barriers = pygame.sprite.Group()
        self.weapons = pygame.sprite.Group()
        self.bullets = pygame.sprite.Group()

        # Создаём башню (со здоровьем 320)
        self.tower = Tower(TOWER_POS, health=600)

        # Счёт игрока
        self.score = 0
        self.money = START_MONEY

        # Шрифты
        self.font_small = pygame.font.SysFont("arial", 20)
        self.font_big = pygame.font.SysFont("arial", 50)

        # Имя игрока (для записи в CSV)
        self.player_name = "Player"

        # Флаги
        self.placing_barrier = False
        self.placing_weapon = False

    def start_screen(self):
        """
        Функция отображения стартового экрана и ожидания нажатия "Старт".
        """
        start_button = Button((WIDTH // 2 - 100, HEIGHT // 2 - 25, 200, 50), "Начать игру")
        name_input_active = False
        input_box = pygame.Rect(WIDTH // 2 - 100, HEIGHT // 2 - 100, 200, 30)

        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if start_button.is_clicked(event.pos):
                        return  # Выходим, чтобы начать игру
                    if input_box.collidepoint(event.pos):
                        name_input_active = True
                    else:
                        name_input_active = False
                elif event.type == pygame.KEYDOWN:
                    if name_input_active:
                        if event.key == pygame.K_BACKSPACE:
                            self.player_name = self.player_name[:-1]
                        else:
                            # Ограничим длину имени
                            if len(self.player_name) < 10:
                                self.player_name += event.unicode

            # Рисуем на экране
            self.screen.fill(GRAY)
            # Текст с именем
            pygame.draw.rect(self.screen, WHITE, input_box)
            name_surface = self.font_small.render(self.player_name, True, BLACK)
            self.screen.blit(name_surface, (input_box.x + 5, input_box.y + 5))

            # Кнопка
            start_button.draw(self.screen)

            text_info = self.font_small.render("Введите имя:", True, BLACK)
            self.screen.blit(text_info, (input_box.x, input_box.y - 25))

            pygame.display.flip()

    def game_loop(self):
        """
        Основной игровой цикл: здесь происходит отыгрывание уровней,
        спавн монстров, размещение баррикад и оружия и т.д.
        """
        while self.running:
            self.clock.tick(FPS)
            if self.current_level_index >= len(self.levels):
                # Все уровни пройдены
                self.running = False
                break

            current_level = self.levels[self.current_level_index]

            # Обработка событий
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_b:
                        # Начинаем/отменяем размещение баррикады
                        self.placing_barrier = not self.placing_barrier
                        self.placing_weapon = False
                    elif event.key == pygame.K_w:
                        # Начинаем/отменяем размещение оружия
                        self.placing_weapon = not self.placing_weapon
                        self.placing_barrier = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    # Размещаем баррикаду/оружие, если нажата соответствующая «кнопка» (B или W)
                    if self.placing_barrier and self.money >= BARRIER_COST:
                        x, y = event.pos
                        # Привязка к "сетке" (можно убрать, если не нужно)
                        x = (x // CELL_SIZE) * CELL_SIZE
                        y = (y // CELL_SIZE) * CELL_SIZE
                        barrier = Barrier(x, y)
                        self.barriers.add(barrier)
                        self.money -= BARRIER_COST
                    elif self.placing_weapon and self.money >= WEAPON_COST:
                        x, y = event.pos
                        x = (x // CELL_SIZE) * CELL_SIZE
                        y = (y // CELL_SIZE) * CELL_SIZE
                        weapon = Weapon(x, y)
                        self.weapons.add(weapon)
                        self.money -= WEAPON_COST

            # Обновляем уровень (спавн монстров)
            current_level.update(self.monsters)

            # Обновляем спрайты
            self.monsters.update(self.tower, self.barriers)
            self.weapons.update(self.monsters, self.bullets)
            self.bullets.update()

            # Проверяем здоровье башни
            if self.tower.health <= 0:
                # Проиграли
                self.running = False
                break

            # Отрисовка
            self.draw()

            # Если все волны уровня прошли и в группе монстров никого не осталось,
            # переходим к следующему уровню
            self.money += 0.01
            if current_level.done and len(self.monsters) == 0:
                self.current_level_index += 1
                # Пополним деньги игрока за пройденный уровень
                self.money += 80
                # Добавим очков
                self.score += 1

    def draw(self):
        """
        Отрисовка игрового поля и всех объектов.
        """
        # «Замостим» фон плиткой (424x119), чтобы покрыть всё окно 800x600
        for x in range(0, WIDTH, self.ground_tile.get_width()):
            for y in range(0, HEIGHT, self.ground_tile.get_height()):
                self.screen.blit(self.ground_tile, (x, y))

        # Рисуем башню
        self.screen.blit(self.tower.image, self.tower.rect.topleft)

        # Рисуем баррикады
        self.barriers.draw(self.screen)
        # Рисуем оружие
        self.weapons.draw(self.screen)
        # Рисуем монстров
        self.monsters.draw(self.screen)
        # Рисуем пули
        self.bullets.draw(self.screen)

        # Текстовое поле: здоровье башни
        tower_health_text = self.font_small.render(f"Башня HP: {self.tower.health}", True, WHITE)
        self.screen.blit(tower_health_text, (10, 10))

        # Деньги
        money_text = self.font_small.render(f"Деньги: {int(self.money)}", True, WHITE)
        self.screen.blit(money_text, (10, 30))

        # Счёт
        score_text = self.font_small.render(f"Счёт: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 50))

        # Подсказка
        hint_text = self.font_small.render("B - поставить барьер, W - поставить оружие", True, WHITE)
        self.screen.blit(hint_text, (10, HEIGHT - 30))

        pygame.display.flip()

    def final_screen(self):
        """
        Экран результата: если башня уничтожена - сообщаем о поражении,
        иначе - о победе. Выводим таблицу рекордов.
        """
        # Если башня жива, значит мы прошли все уровни
        success = self.tower.health > 0

        # Сохраняем результат
        self.score_table.add_record(self.player_name, self.score)

        # Получим лучшие результаты
        best_scores = self.score_table.get_best_scores(5)

        # Кнопка "Выход"
        exit_button = Button((WIDTH // 2 - 100, HEIGHT // 2 + 150, 200, 50), "Выход", color=(200, 50, 50))

        while True:
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if exit_button.is_clicked(event.pos):
                        pygame.quit()
                        sys.exit()

            self.screen.fill(GRAY)

            if success:
                text = self.font_big.render("ПОБЕДА!", True, GREEN)
            else:
                text = self.font_big.render("ПОРАЖЕНИЕ!", True, RED)

            text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 100))
            self.screen.blit(text, text_rect)

            # Выводим наши очки
            score_text = self.font_small.render(f"Ваш счёт: {self.score}", True, BLACK)
            self.screen.blit(score_text, (WIDTH // 2 - 50, HEIGHT // 2 - 50))

            # Лучшая таблица
            y_offset = HEIGHT // 2
            self.screen.blit(self.font_small.render("Топ-результаты:", True, BLACK), (WIDTH // 2 - 50, y_offset))
            y_offset += 20
            for i, (name, sc) in enumerate(best_scores):
                record_str = f"{i + 1}. {name} - {sc}"
                self.screen.blit(self.font_small.render(record_str, True, BLACK), (WIDTH // 2 - 50, y_offset))
                y_offset += 20

            exit_button.draw(self.screen)

            pygame.display.flip()


# -----------------------------------------------------------------------------------
# ------------------------ ГЛАВНАЯ ФУНКЦИЯ -------------------------------------------
# -----------------------------------------------------------------------------------
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    game = TowerDefenceGame(screen)

    # Стартовое меню
    game.start_screen()

    # Игровой процесс
    game.game_loop()

    # Финальный экран
    game.final_screen()


if __name__ == "__main__":
    main()
