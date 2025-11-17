import sqlite3
import sys
import random
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QProgressBar, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem,
    QFrame, QSplitter, QDialog, QGridLayout)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPixmap, QBrush, QTransform

#КОНСТАНТЫ
# Размеры окна и сцены
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
SCENE_WIDTH = 800
SCENE_HEIGHT = 600
# Размеры спрайтов
PLAYER_SIZE = 50
ENEMY_SIZE = 60
ITEM_SIZE = 30
# Тайминги
GAME_LOOP_INTERVAL = 50
ENEMY_SPAWN_INTERVAL = 5000
ENEMY_MOVE_INTERVAL = 1000
# Базовые характеристики игрока
BASE_HEALTH = 100
BASE_MANA = 100
BASE_ATTACK = 10
BASE_DEFENSE = 5
# Опыт и уровни
EXP_PER_LEVEL = 100
LEVEL_15_REQUIRED = 15
# Цены
WEAPON_UPGRADE_PRICE = 50
ARMOR_UPGRADE_PRICE = 50
STRONG_ATTACK_PRICE = 500
TAVERN_PRICE = 10
# Шансы (0.0 - 1.0)
MINE_SUCCESS_CHANCE = 0.1
ESCAPE_CHANCE = 0.2
HEAVENLY_STRIKE_CHANCE = 0.7
ITEM_SPAWN_CHANCE = 0.3
# Лимиты
MAX_ENEMIES = 5
ENEMY_ATTACK_RANGE = 100
ITEM_PICKUP_RANGE = 50
# Боевые множители
STRONG_ATTACK_MULTIPLIER = 1.5
HEAVENLY_STRIKE_MULTIPLIER = 2.0
# Восстановление
HEALTH_POTION_RESTORE = 50
MANA_POTION_RESTORE = 30
MEDITATION_RESTORE = 20
# Теневая форма
LEVEL_FOR_SHADOW = 100
SHADOW_SIZE = 70


class Player(QGraphicsPixmapItem):
    """Класс игрока с характеристиками и управлением"""
    def __init__(self, game=None):
        super().__init__()
        self.facing_right = True
        self.game = game  # Основная игра для доступа к базе данных
        # Загрузка текстурки персонажа
        self.original_pixmap = QPixmap("Pictures/hero.png")
        self.original_pixmap = self.original_pixmap.scaled(
            PLAYER_SIZE, PLAYER_SIZE, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.setPixmap(self.original_pixmap)
        # Начальная позиция и характеристики
        self.setPos(400, 300)
        self.health = BASE_HEALTH
        self.mana = BASE_MANA
        self.level = 1
        self.exp = 0
        self.attack_power = BASE_ATTACK
        self.defense = BASE_DEFENSE
        self.shadow_form = False
        self.shadow_timer = QTimer()
        self.shadow_timer.timeout.connect(self.end_shadow_form)

    def move(self, dx, dy):
        """Движение игрока с проверкой границ и зеркальным отображением"""
        new_x = self.x() + dx
        new_y = self.y() + dy
        # Проверка границ поля
        if 0 <= new_x <= 750 and 0 <= new_y <= 550:
            self.setPos(new_x, new_y)
        # Зеркальное отображение текстуры при изменении направления взгляда
        if dx < 0 and self.facing_right:
            mirrored_pixmap = self.original_pixmap.transformed(QTransform().scale(-1, 1))
            self.setPixmap(mirrored_pixmap)
            self.facing_right = False
        elif dx > 0 and not self.facing_right:
            self.setPixmap(self.original_pixmap)
            self.facing_right = True

    def activate_shadow_form(self):
        """Активация формы Тени Забвения"""
        if not self.shadow_form:
            self.shadow_form = True
            # Сохраняем оригинальные характеристики
            self.original_pixmap_backup = self.original_pixmap
            self.original_health = self.health
            self.original_mana = self.mana
            self.original_attack = self.attack_power
            self.original_defense = self.defense
            # Устанавливаем текстуру тени
            shadow_pixmap = QPixmap("Pictures/shadow.png")
            if self.facing_right:
                shadow_pixmap = shadow_pixmap.transformed(QTransform().scale(-1, 1))
            shadow_pixmap = shadow_pixmap.scaled(SHADOW_SIZE, SHADOW_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
            self.setPixmap(shadow_pixmap)
            # безграничная сила(ведь кто-то аж до 100 lvl поднялся)
            self.health = float('999999999')
            self.mana = float('999999999')
            self.attack_power = float('999999999')
            self.defense = float('999999999')
            if self.game:
                self.game.add_log("🌑 ТЬМА ПОГЛОЩАЕТ ВАС! Вы становитесь Тенью Забвения!")

    def end_shadow_form(self):
        """Завершение формы Тени Забвения"""
        if self.shadow_form:
            self.shadow_form = False
            self.shadow_timer.stop()
            # Восстанавливаем оригинальные характеристики
            if not self.facing_right:
                self.original_pixmap_backup = self.original_pixmap_backup.transformed(QTransform().scale(-1, 1))
            self.setPixmap(self.original_pixmap_backup)
            self.health = self.original_health
            self.mana = self.original_mana
            self.attack_power = self.original_attack
            self.defense = self.original_defense
            if self.game:
                self.game.add_log("⚡ Сила Тени покидает вас...")
                self.game.update_stats_display()

    def shadow_attack(self, enemy):
        """Атака в форме тени - мгновенное убийство"""
        if self.shadow_form:
            enemy.health = 0
            return True
        return False


class Enemy(QGraphicsPixmapItem):
    """Класс врагов"""
    def __init__(self, enemy_type, level):
        super().__init__()
        self.enemy_type = enemy_type
        self.level = level
        # загрузка текстуры врага
        filename = f"Pictures/{enemy_type}.png"
        self.original_pixmap = QPixmap(filename)
        self.original_pixmap = self.original_pixmap.scaled(
            ENEMY_SIZE, ENEMY_SIZE, Qt.AspectRatioMode.KeepAspectRatio
        )
        self.setPixmap(self.original_pixmap)
        # характеристики для разных типов врагов
        if enemy_type == 'goblin':
            base_health = 10
            base_attack_power = 2
            base_exp_reward = 5
            base_gold_reward = 2
        elif enemy_type == 'orc':
            base_health = 20
            base_attack_power = 5
            base_exp_reward = 10
            base_gold_reward = 5
        elif enemy_type == 'dragon':
            base_health = 40  # Самое высокое здоровье
            base_attack_power = 10
            base_exp_reward = 20
            base_gold_reward = 10
        # Установка характеристик с учетом уровня
        self.health = base_health * level
        self.attack_power = base_attack_power * level
        self.exp_reward = base_exp_reward * level
        self.gold_reward = random.randint(1, base_gold_reward) * level
        # Таймер для случайного движения врагов
        self.move_timer = QTimer()
        self.move_timer.timeout.connect(self.move_randomly)
        self.move_timer.start(ENEMY_MOVE_INTERVAL)  # Движение каждую секунду

    def move_randomly(self):
        """Случайное движение врага"""
        dx = random.randint(-5, 5)
        dy = random.randint(-5, 5)
        new_x = self.x() + dx
        new_y = self.y() + dy
        # Ограничение движения в пределах поля
        if 0 <= new_x <= 760 and 0 <= new_y <= 560:
            self.setPos(new_x, new_y)


class Item(QGraphicsPixmapItem):
    """Класс для предметов, которые можно собирать по карте"""
    def __init__(self, item_type):
        super().__init__()
        self.item_type = item_type
        filename = f"Pictures/{item_type}.png"
        pixmap = QPixmap(filename)
        pixmap = pixmap.scaled(ITEM_SIZE, ITEM_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
        self.setPixmap(pixmap)


class Tavern(QGraphicsRectItem):
    def __init__(self):
        super().__init__(0, 0, 60, 60)
        self.setBrush(QBrush(QColor(139, 69, 19)))  # Коричневый цвет
        self.setPos(700, 50)


class RPGGame(QMainWindow):
    """Основной класс, способный править всеми"""
    def __init__(self):
        super().__init__()
        self.init_db()
        self.current_user = None
        self.scene = None
        self.player = None
        self.enemies = []
        self.items = []
        self.tavern = None
        self.current_zone = "forest"
        self.game_timer = QTimer()
        self.enemy_spawn_timer = QTimer()
        self.initUI()

    def init_db(self):
        """Редактирование базы данных и создание таблиц"""
        self.conn = sqlite3.connect('rpg_game.db')
        self.cursor = self.conn.cursor()
        # Основная таблица игроков
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                health INTEGER DEFAULT 100,
                mana INTEGER DEFAULT 100,
                attack_power INTEGER DEFAULT 10,
                defense INTEGER DEFAULT 5,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        ''')
        try:
            self.cursor.execute("SELECT gold FROM players LIMIT 1")
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS players_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    exp INTEGER DEFAULT 0,
                    health INTEGER DEFAULT 100,
                    mana INTEGER DEFAULT 100,
                    attack_power INTEGER DEFAULT 10,
                    defense INTEGER DEFAULT 5,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
            ''')
            # Перенос данных
            self.cursor.execute('''
                INSERT OR IGNORE INTO players_new 
                SELECT id, username, password, level, exp, health, mana, 
                       attack_power, defense, created_date 
                FROM players
            ''')
            # Перенос золота в инвентарь
            self.cursor.execute('SELECT id, gold FROM players WHERE gold > 0')
            players_with_gold = self.cursor.fetchall()
            for player_id, gold_amount in players_with_gold:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO inventory (player_id, item_type, quantity)
                    VALUES (?, 'gold', ?)
                ''', (player_id, gold_amount))
            # Замена старой таблицы
            self.cursor.execute('DROP TABLE players')
            self.cursor.execute('ALTER TABLE players_new RENAME TO players')
        except sqlite3.OperationalError:
            pass
        # Дополнительные таблицы
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                item_type TEXT,
                quantity INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players (id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                action_type TEXT,
                description TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players (id))
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                achievement_name TEXT,
                achieved_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player_id) REFERENCES players (id))
        ''')
        # Таблица для навыков
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER,
                skill_name TEXT,
                unlocked BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (player_id) REFERENCES players (id),
                UNIQUE(player_id, skill_name)
            )
        ''')
        self.conn.commit()

    def initUI(self):
        """Пользовательский интерфейс"""
        self.setWindowTitle('RPG Adventure Game')
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        # Украшение интерфейса
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                border: 2px solid #1f618d;
                border-radius: 10px;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
                min-width: 100px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5dade2, stop:1 #3498db);
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit, QTextEdit {
                background: #34495e;
                border: 2px solid #5dade2;
                border-radius: 8px;
                padding: 6px;
                font-size: 14px;
                color: white;
            }
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ff0000, stop:1 #ff9900);
            }
            QTableWidget {
                background: #2c3e50;
                color: white;
                gridline-color: #34495e;
            }
            QHeaderView::section {
                background: #3498db;
                color: white;
                font-weight: bold;
            }
        """)
        self.show_login_screen()

    def show_login_screen(self):
        """Экран входа в игру"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Фон экрана входа
        background_pixmap = QPixmap("Pictures/login_bg.png")
        background_label = QLabel()
        background_label.setPixmap(
            background_pixmap.scaled(1500, 800, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        )
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout = QVBoxLayout()
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Заголовок и подзаголовок
        title = QLabel('The shadow of oblivion')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 32, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #e74c3c; background-color: rgba(0,0,0,0.5); padding: 20px; border-radius: 10px;"
        )
        overlay_layout.addWidget(title)
        subtitle = QLabel('Эпическое приключение ждет!')
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont('Arial', 16))
        subtitle.setStyleSheet(
            "color: #f39c12; background-color: rgba(0,0,0,0.5); padding: 10px; border-radius: 5px;"
        )
        overlay_layout.addWidget(subtitle)
        # Поля ввода
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText('Имя героя')
        self.username_input.setMaximumWidth(300)
        self.username_input.setStyleSheet("background-color: rgba(0,0,0,0.7);")
        overlay_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Магический пароль')
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMaximumWidth(300)
        self.password_input.setStyleSheet("background-color: rgba(0,0,0,0.7);")
        overlay_layout.addWidget(self.password_input)
        # Кнопки входа и регистрации
        buttons_layout = QHBoxLayout()
        login_btn = QPushButton('Войти в мир')
        login_btn.clicked.connect(self.login)
        login_btn.setStyleSheet("background-color: rgba(52, 152, 219, 0.8);")
        buttons_layout.addWidget(login_btn)

        register_btn = QPushButton('Создать героя')
        register_btn.clicked.connect(self.register)
        register_btn.setStyleSheet("background-color: rgba(46, 204, 113, 0.8);")
        buttons_layout.addWidget(register_btn)
        overlay_layout.addLayout(buttons_layout)

        background_label.setLayout(overlay_layout)
        layout.addWidget(background_label)
        central_widget.setLayout(layout)

    def login(self):
        """Вход игрока"""
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            self.show_message('Предупреждение', 'Заполните все поля, путник!', QMessageBox.Icon.Warning)
            return
        self.cursor.execute(
            'SELECT * FROM players WHERE username = ? AND password = ?',
            (username, password)
        )
        user = self.cursor.fetchone()
        if user:
            self.current_user = user
            self.ensure_base_skills()
            self.log_game_action('login', f'Герой {username} вошел в мир')
            self.show_main_menu()
        else:
            self.show_message('Ошибка', 'Неверное имя героя или магический пароль!', QMessageBox.Icon.Warning)

    def register(self):
        """Регистрация нового игрока"""
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            self.show_message('Предупреждение', 'Заполните все поля, путник!', QMessageBox.Icon.Warning)
            return
        try:
            self.cursor.execute(
                'INSERT INTO players (username, password) VALUES (?, ?)',
                (username, password)
            )
            self.conn.commit()

            self.cursor.execute('SELECT * FROM players WHERE username = ?', (username,))
            self.current_user = self.cursor.fetchone()
            self.ensure_base_skills()

            self.log_game_action('register', f'Создан новый герой: {username}')
            self.show_message('Успех', f'Герой {username} создан! Добро пожаловать в мир, полный приключений!')
            self.show_main_menu()

        except sqlite3.IntegrityError:
            self.show_message('Ошибка', 'Какой-то герой уже наречен этим именем!', QMessageBox.Icon.Warning)

    def show_main_menu(self):
        """Главное меню игры"""
        # Остановка игровых таймеров
        self.stop_game_timers()
        # Сохранение прогресса
        if self.player and self.current_user:
            self.save_player_progress()
        # Сброс игрового состояния
        self.reset_game_state()
        # Обновление данных игрока
        if self.current_user:
            self.cursor.execute('SELECT * FROM players WHERE id = ?', (self.current_user[0],))
            self.current_user = self.cursor.fetchone()
        # Создание главного меню
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        menu_bg = QPixmap("Pictures/menu_bg.png")
        background_label = QLabel()
        background_label.setPixmap(
            menu_bg.scaled(1400, 750, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        )
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay_layout = QVBoxLayout()
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Приветствие и статистика
        welcome_label = QLabel(f'Добро пожаловать, {self.current_user[1]}!')
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setFont(QFont('Arial', 24, QFont.Weight.Bold))
        welcome_label.setStyleSheet(
            "color: #f39c12; background-color: rgba(0,0,0,0.7); padding: 15px; border-radius: 10px;"
        )
        overlay_layout.addWidget(welcome_label)

        current_health = self.current_user[5] if len(self.current_user) > 5 else BASE_HEALTH
        if current_health < 0:
            current_health = 0
        gold_amount = self.get_gold_amount()
        stats_label = QLabel(
            f'Уровень: {self.current_user[3]} | Золото: {gold_amount} | Здоровье: {current_health}/{BASE_HEALTH}'
        )
        stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,0.7); padding: 10px; border-radius: 5px;"
        )
        overlay_layout.addWidget(stats_label)
        # Кнопки меню
        menu_buttons = [
            (f'Посетить таверну ({TAVERN_PRICE} золота)', self.visit_tavern, "rgba(230, 126, 34, 0.8)"),
            ('Магазин', self.show_shop, "rgba(155, 89, 182, 0.8)"),
            ('Начать приключение', self.start_game, "rgba(52, 152, 219, 0.8)"),
            ('Инвентарь', self.show_inventory, "rgba(52, 152, 219, 0.8)"),
            ('Характеристики', self.show_player_stats, "rgba(52, 152, 219, 0.8)"),
            ('Достижения', self.show_achievements, "rgba(52, 152, 219, 0.8)"),
            ('История приключений', self.show_game_history, "rgba(52, 152, 219, 0.8)"),
            ('⛏️ Шахта', self.show_mine, "rgba(230, 126, 34, 0.8)"),
            ('Выйти из мира', self.show_login_screen, "rgba(231, 76, 60, 0.8)")
        ]
        for text, handler, color in menu_buttons:
            btn = QPushButton(text)
            btn.clicked.connect(handler)
            if "font-size" in text:
                btn.setStyleSheet(f"font-size: 16px; padding: 12px; background: {color}; color: white;")
            else:
                btn.setStyleSheet(f"background: {color}; color: white;")
            overlay_layout.addWidget(btn)
        background_label.setLayout(overlay_layout)
        central_widget_layout = QVBoxLayout(central_widget)
        central_widget_layout.addWidget(background_label)

    def show_shop(self):
        """ Магазин для покупки улучшений"""
        background_label = QLabel()
        background_label.setStyleSheet("background-color: #141013;")
        background_pixmap = QPixmap("Pictures/shop_bg.png")
        background_pixmap = background_pixmap.scaled(
            WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        overlay_layout = QVBoxLayout()
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('🏪 МАГАЗИН')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #9b59b6; background-color: rgba(0,0,0,0.7); padding: 15px; border-radius: 10px;"
        )
        overlay_layout.addWidget(title)
        # текущее золото
        gold_amount = self.get_gold_amount()
        gold_label = QLabel(f'💰 Ваше золото: {gold_amount}')
        gold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        gold_label.setFont(QFont('Arial', 14))
        gold_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,0.5); padding: 10px; border-radius: 5px;"
        )
        overlay_layout.addWidget(gold_label)
        # Список товаров
        items_frame = QFrame()
        items_frame.setFrameStyle(QFrame.Shape.Box)
        items_frame.setStyleSheet("background-color: rgba(0,0,0,0.5); padding: 10px; border-radius: 10px;")
        items_layout = QVBoxLayout(items_frame)
        # Улучшение оружия
        weapon_upgrade_layout = QHBoxLayout()
        weapon_upgrade_label = QLabel(f'⚔️ Улучшение оружия (+5 атаки) - {WEAPON_UPGRADE_PRICE} золота')
        weapon_upgrade_label.setStyleSheet("color: white;")
        weapon_upgrade_btn = QPushButton('Купить')
        weapon_upgrade_btn.clicked.connect(lambda: self.buy_weapon_upgrade(WEAPON_UPGRADE_PRICE))
        weapon_upgrade_layout.addWidget(weapon_upgrade_label)
        weapon_upgrade_layout.addWidget(weapon_upgrade_btn)
        items_layout.addLayout(weapon_upgrade_layout)
        # Улучшение брони
        armor_upgrade_layout = QHBoxLayout()
        armor_upgrade_label = QLabel(f'🛡️ Улучшение брони (+5 защиты) - {ARMOR_UPGRADE_PRICE} золота')
        armor_upgrade_label.setStyleSheet("color: white;")
        armor_upgrade_btn = QPushButton('Купить')
        armor_upgrade_btn.clicked.connect(lambda: self.buy_armor_upgrade(ARMOR_UPGRADE_PRICE))
        armor_upgrade_layout.addWidget(armor_upgrade_label)
        armor_upgrade_layout.addWidget(armor_upgrade_btn)
        items_layout.addLayout(armor_upgrade_layout)
        # Навык "Сильная атака"
        strong_attack_layout = QHBoxLayout()
        strong_attack_label = QLabel(f'💥 Навык "Сильная атака" - {STRONG_ATTACK_PRICE} золота')
        strong_attack_label.setStyleSheet("color: white;")
        strong_attack_btn = QPushButton('Купить')
        strong_attack_btn.clicked.connect(lambda: self.buy_skill('strong_attack', STRONG_ATTACK_PRICE))

        if self.is_skill_unlocked('strong_attack'):
            strong_attack_btn.setEnabled(False)
            strong_attack_btn.setText('Куплено')

        strong_attack_layout.addWidget(strong_attack_label)
        strong_attack_layout.addWidget(strong_attack_btn)
        items_layout.addLayout(strong_attack_layout)
        overlay_layout.addWidget(items_frame)
        # Кнопка возврата в меню
        close_btn = QPushButton('Назад')
        close_btn.clicked.connect(self.show_main_menu)
        close_btn.setStyleSheet("background-color: rgba(231, 76, 60, 0.8); color: white;")
        overlay_layout.addWidget(close_btn)
        background_label.setLayout(overlay_layout)
        self.setCentralWidget(background_label)

    def buy_skill(self, skill_name, price):
        """Покупка навыка"""
        gold_amount = self.get_gold_amount()
        if gold_amount >= price:
            self.remove_item_from_inventory('gold', price)
            # Добавление навыка в базу данных
            self.cursor.execute(
                'INSERT OR REPLACE INTO player_skills (player_id, skill_name, unlocked) VALUES (?, ?, TRUE)',
                (self.current_user[0], skill_name)
            )
            self.conn.commit()
            self.show_message('Успешная покупка!', f'Навык "{skill_name}" теперь доступен!')
            self.log_game_action('shop', f'Куплен навык {skill_name} за {price} золота')
            # Обновление магазина
            self.update_shop_gold_display()
            self.update_shop_buttons()
        else:
            self.show_message(
                'Ошибка',
                f'Недостаточно золота! Нужно {price} золота.',
                QMessageBox.Icon.Warning)

    def update_shop_buttons(self):
        """Обновление кнопок в магазине"""
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow) and widget.windowTitle() == 'Магазин':
                # Поиск кнопки покупки сильной атаки
                strong_attack_btn = None
                for child in widget.findChildren(QPushButton):
                    if ('Сильная атака' in child.text() or
                            (hasattr(child, 'skill_name') and
                             getattr(child, 'skill_name') == 'strong_attack')):
                        strong_attack_btn = child
                        break

                if strong_attack_btn and self.is_skill_unlocked('strong_attack'):
                    strong_attack_btn.setEnabled(False)
                    strong_attack_btn.setText('Куплено')

    def is_skill_unlocked(self, skill_name):
        """Проверяем, открыт ли навык у игрока"""
        self.cursor.execute(
            'SELECT unlocked FROM player_skills WHERE player_id = ? AND skill_name = ?',
            (self.current_user[0], skill_name))
        result = self.cursor.fetchone()
        return result and result[0]

    def buy_weapon_upgrade(self, price):
        """Покупка улучшения оружия"""
        gold_amount = self.get_gold_amount()
        if gold_amount >= price:
            self.remove_item_from_inventory('gold', price)
            self.cursor.execute(
                'UPDATE players SET attack_power = attack_power + 5 WHERE id = ?',
                (self.current_user[0],)
            )
            self.conn.commit()
            self.show_message('Успешная покупка!', 'Оружие улучшено! +5 к атаке')
            self.log_game_action('shop', f'Улучшение оружия за {price} золота')
            self.show_main_menu()
        else:
            self.show_message(
                'Ошибка',
                f'Недостаточно золота! Нужно {price} золота.',
                QMessageBox.Icon.Warning
            )

    def buy_armor_upgrade(self, price):
        """Покупка улучшения брони"""
        gold_amount = self.get_gold_amount()
        if gold_amount >= price:
            self.remove_item_from_inventory('gold', price)
            self.cursor.execute(
                'UPDATE players SET defense = defense + 5 WHERE id = ?',
                (self.current_user[0],)
            )
            self.conn.commit()
            self.show_message('Успешная покупка!', 'Броня улучшена! +5 к защите')
            self.log_game_action('shop', f'Улучшение брони за {price} золота')
            self.show_main_menu()
        else:
            self.show_message(
                'Ошибка',
                f'Недостаточно золота! Нужно {price} золота.',
                QMessageBox.Icon.Warning
            )

    def update_shop_gold_display(self):
        """Обновление золота в магазине"""
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow) and widget.windowTitle() == 'Магазин':
                for label in widget.findChildren(QLabel):
                    if 'золото' in label.text().lower():
                        gold_amount = self.get_gold_amount()
                        label.setText(f'Ваше золото: {gold_amount}')
                        break

    def ensure_base_skills(self):
        """Гарантирует наличие базовых навыков"""
        base_skills = ['basic_attack', 'meditation']
        for skill in base_skills:
            self.cursor.execute('''
                INSERT OR IGNORE INTO player_skills (player_id, skill_name, unlocked) 
                VALUES (?, ?, TRUE)
            ''', (self.current_user[0], skill))
        self.conn.commit()

    def start_game(self):
        """Запуск игрового процесса"""
        # Проверка здоровья перед игрой
        current_health = self.current_user[5] if len(self.current_user) > 5 else BASE_HEALTH
        if current_health <= 0:
            self.show_message(
                'Ошибка',
                'Невозможно начать приключение.\nВаше здоровье равно 0!\nПосетите таверну для лечения.',
                QMessageBox.Icon.Warning
            )
            return
        # Остановка и перезапуск таймеров
        self.stop_game_timers()
        self.game_timer = QTimer()
        self.enemy_spawn_timer = QTimer()
        self.enemies = []
        self.items = []
        # Создание интерфейса
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        # Левая панель игровое поле
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self.graphics_view = QGraphicsView()
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT)
        # Установка фона поля битвы
        battle_bg = QPixmap("Pictures/battle_bg.png")
        self.scene.setBackgroundBrush(
            QBrush(battle_bg.scaled(SCENE_WIDTH, SCENE_HEIGHT, Qt.AspectRatioMode.KeepAspectRatioByExpanding))
        )
        # Создание персонажа
        self.player = Player(self)
        if len(self.current_user) >= 9:
            self.player.level = self.current_user[3] or 1
            self.player.exp = self.current_user[4] or 0
            self.player.health = self.current_user[5] or BASE_HEALTH
            self.player.mana = BASE_MANA
            self.player.attack_power = self.current_user[7] or BASE_ATTACK
            self.player.defense = self.current_user[8] or BASE_DEFENSE
        else:
            # Резервные значения по умолчанию
            self.player.level = 1
            self.player.exp = 0
            self.player.health = BASE_HEALTH
            self.player.mana = BASE_MANA
            self.player.attack_power = BASE_ATTACK
            self.player.defense = BASE_DEFENSE

        self.scene.addItem(self.player)
        self.graphics_view.setScene(self.scene)
        left_layout.addWidget(self.graphics_view)
        # Информация об управлении
        controls_info = QLabel('Управление: WASD - движение, Space - атака, E - подобрать предмет')
        controls_info.setStyleSheet("color: #f39c12; font-size: 12px;")
        left_layout.addWidget(controls_info)
        # Правая панель - статистика и информация
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        # шкалы здоровья, маны и опыта
        self.health_bar = QProgressBar()
        self.health_bar.setMaximum(BASE_HEALTH)
        self.health_bar.setValue(self.player.health)
        self.health_bar.setFormat('Здоровье: %v/%m')
        self.health_bar.setStyleSheet('color: black')
        right_layout.addWidget(self.health_bar)

        self.mana_bar = QProgressBar()
        self.mana_bar.setMaximum(BASE_MANA)
        self.mana_bar.setValue(BASE_MANA)
        self.mana_bar.setFormat('Мана: %v/%m')
        self.mana_bar.setStyleSheet("""
            QProgressBar { color: black; }
            QProgressBar::chunk { background: #3498db; }
        """)
        right_layout.addWidget(self.mana_bar)

        self.exp_bar = QProgressBar()
        self.exp_bar.setMaximum(100)
        self.exp_bar.setValue(self.player.exp % 100)
        self.exp_bar.setFormat('Опыт: %v/%m')
        self.exp_bar.setStyleSheet("""
            QProgressBar { color: black; }
            QProgressBar::chunk { background: #9b59b6; }
        """)
        right_layout.addWidget(self.exp_bar)
        # Статистика персонажа
        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.Shape.Box)
        stats_layout = QVBoxLayout(stats_frame)
        self.level_label = QLabel(f'Уровень: {self.player.level}')
        stats_layout.addWidget(self.level_label)

        gold_amount = self.get_gold_amount()
        self.gold_label = QLabel(f'Золото: {gold_amount}')
        stats_layout.addWidget(self.gold_label)

        self.attack_label = QLabel(f'Атака: {self.player.attack_power}')
        stats_layout.addWidget(self.attack_label)

        self.defense_label = QLabel(f'Защита: {self.player.defense}')
        stats_layout.addWidget(self.defense_label)
        right_layout.addWidget(stats_frame)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setReadOnly(True)
        right_layout.addWidget(self.log_text)
        # Кнопка возврата в меню
        buttons_layout = QHBoxLayout()
        menu_btn = QPushButton('Вернуться')
        menu_btn.clicked.connect(self.show_main_menu)
        buttons_layout.addWidget(menu_btn)
        right_layout.addLayout(buttons_layout)
        # Настройка разделителя
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([800, 400])
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(splitter)
        # Запуск игровых таймеров
        self.game_timer.timeout.connect(self.game_loop)
        self.game_timer.start(GAME_LOOP_INTERVAL)
        self.enemy_spawn_timer.timeout.connect(self.spawn_enemy)
        self.enemy_spawn_timer.start(ENEMY_SPAWN_INTERVAL)
        self.add_log("Добро пожаловать в мир приключений! Ищите врагов и сокровища!")

    def spawn_enemy(self):
        """Создание нового врага"""
        if self.scene and self.player and len(self.enemies) < MAX_ENEMIES:
            enemy_types = ['goblin', 'orc', 'dragon']
            enemy_type = random.choice(enemy_types)
            level = max(1, self.player.level - 1 + random.randint(0, 2))
            enemy = Enemy(enemy_type, level)
            x = random.randint(50, 750)
            y = random.randint(50, 550)
            enemy.setPos(x, y)
            self.scene.addItem(enemy)
            self.enemies.append(enemy)
            # Остановка движения врагов если идет битва
            if hasattr(self, 'battle_system') and self.battle_system.is_battle_active:
                if enemy.move_timer.isActive():
                    enemy.move_timer.stop()
            # Случайное создание предмета рядом с врагом
            if random.random() < ITEM_SPAWN_CHANCE:
                self.spawn_item_near_enemy(enemy)

    def spawn_item_near_enemy(self, enemy):
        """Создание предмета рядом с врагом"""
        item_types = ['health_potion', 'mana_potion', 'gold', 'weapon', 'armor']
        item_type = random.choice(item_types)
        item = Item(item_type)
        offset_x = random.randint(-20, 20)
        offset_y = random.randint(-20, 20)
        item.setPos(enemy.x() + offset_x, enemy.y() + offset_y)
        self.scene.addItem(item)
        self.items.append(item)

    def collect_item(self, item):
        """ подбор предмета"""
        self.scene.removeItem(item)
        self.items.remove(item)
        # разные типов предметов
        if item.item_type == 'health_potion':
            self.player.health = min(BASE_HEALTH, self.player.health + HEALTH_POTION_RESTORE)
            self.health_bar.setValue(int(self.player.health))
            self.add_log("Выпито зелье здоровья! +30 HP")

        elif item.item_type == 'mana_potion':
            self.player.mana = min(BASE_MANA, self.player.mana + MANA_POTION_RESTORE)
            self.mana_bar.setValue(int(self.player.mana))
            self.add_log("Выпито зелье маны! +30 MP")

        elif item.item_type == 'gold':
            gold_amount = random.randint(5, 20)
            self.add_log(f"Найдено {gold_amount} золота!")
            self.add_item_to_inventory('gold', gold_amount)
            self.update_gold_display()

        elif item.item_type == 'weapon':
            self.player.attack_power += 2
            self.add_log("Найдены обломки оружия! +2 к атаке")
            self.add_item_to_inventory('weapon', 1)

        elif item.item_type == 'armor':
            self.player.defense += 2
            self.add_log("Найдены обломки брони! +2 к защите")
            self.add_item_to_inventory('armor', 1)

        self.update_stats_display()
        self.log_game_action('item_collect', f'Подобран предмет: {item.item_type}')

    def defeat_enemy(self, enemy):
        """Победа над врагом"""
        # Остановка движения врага
        if hasattr(enemy, 'move_timer') and enemy.move_timer.isActive():
            enemy.move_timer.stop()
        self.scene.removeItem(enemy)
        self.enemies.remove(enemy)
        # Награда за победу
        exp_gained = enemy.exp_reward
        gold_gained = enemy.gold_reward
        self.player.exp += exp_gained
        self.add_log(f"Победа! Получено {exp_gained} опыта и {gold_gained} золота!")
        self.add_item_to_inventory('gold', gold_gained)
        self.update_gold_display()
        self.update_stats_display()
        self.check_level_up()
        self.log_game_action('battle', f'Победил {enemy.enemy_type} уровня {enemy.level}')

    def check_level_up(self):
        """Проверка повышения уровня"""
        exp_needed = self.player.level * EXP_PER_LEVEL
        if self.player.exp >= exp_needed:
            self.player.level += 1
            self.player.exp -= exp_needed
            self.player.attack_power += 3
            self.player.defense += 2
            self.add_log(f"Уровень повышен! Теперь вы уровня {self.player.level}!")
            self.update_stats_display()
            # Автоматическое открытие Небесного удара на 15 уровне
            if self.player.level >= LEVEL_15_REQUIRED and not self.is_skill_unlocked('heavenly_strike'):
                self.cursor.execute(
                    'INSERT OR REPLACE INTO player_skills (player_id, skill_name, unlocked) VALUES (?, ?, TRUE)',
                    (self.current_user[0], 'heavenly_strike')
                )
                self.conn.commit()
                self.add_log("🌟 Открыт новый навык: Небесный удар!")
            if self.player.level >= LEVEL_FOR_SHADOW:
                self.add_log("🌌 Вы достигли необходимого уровня! Тень Забвения ждет своего часа...")
            self.log_game_action('level_up', f'Достигнут уровень {self.player.level}')
            self.check_achievements()

    def update_stats_display(self):
        """Обновление статистики игрока"""
        self.level_label.setText(f'Уровень: {self.player.level}')
        self.attack_label.setText(f'Атака: {self.player.attack_power}')
        self.defense_label.setText(f'Защита: {self.player.defense}')
        self.exp_bar.setValue(self.player.exp % 100)
        self.health_bar.setValue(int(self.player.health))
        self.mana_bar.setValue(int(self.player.mana))

    def add_log(self, message):
        """Добавление сообщения"""
        self.log_text.append(f"{message}")
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum())

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if self.player and self.scene:
            if event.key() == Qt.Key.Key_W or event.text().upper() == 'Ц':
                self.player.move(0, -5)
            elif event.key() == Qt.Key.Key_S or event.text().upper() == 'Ы':
                self.player.move(0, 5)
            elif event.key() == Qt.Key.Key_A or event.text().upper() == 'Ф':
                self.player.move(-5, 0)
            elif event.key() == Qt.Key.Key_D or event.text().upper() == 'В':
                self.player.move(5, 0)
            elif event.key() == Qt.Key.Key_Space:
                self.attack_nearest_enemy()
            elif event.key() == Qt.Key.Key_E:
                self.try_pickup_item()

    def attack_nearest_enemy(self):
        """Запуск пошаговой битвы ближайшим врагом"""
        if not self.player or not self.scene:
            return

        nearest_enemy = None
        min_distance = float('inf')
        # Выбор ближайшего врага
        for enemy in self.enemies:
            distance = ((self.player.x() - enemy.x()) ** 2 +
                        (self.player.y() - enemy.y()) ** 2) ** 0.5
            if distance < min_distance and distance < ENEMY_ATTACK_RANGE:
                min_distance = distance
                nearest_enemy = enemy

        if nearest_enemy:
            # Запуск пошаговой битвы
            if not hasattr(self, 'battle_system'):
                self.battle_system = BattleSystem(self)
            self.battle_system.start_battle(nearest_enemy)
        else:
            self.add_log("Нет врагов поблизости!")

    def game_loop(self):
        """Основной игровой цикл"""
        if self.player and self.scene:
            self.check_enemy_collision_damage()

    def check_enemy_collision_damage(self):
        """Столкновения с врагами и нанесение урона"""
        for enemy in self.enemies:
            if self.player.collidesWithItem(enemy):
                # Урон при касании
                damage = max(1, enemy.attack_power // 10)  # 10% от силы атаки
                self.player.health -= damage
                self.health_bar.setValue(int(self.player.health))

                if self.player.health <= 0:
                    self.game_over()
                    break
                # сообщение о полученном уроне(чтоб не спамить)
                if random.random() < 0.1: # шанс 10 %
                    self.add_log(f"{enemy.enemy_type} ранит вас! -{damage} HP")

    def try_pickup_item(self):
        """Попытка подобрать предмет"""
        if not self.player:
            return
        for item in self.items[:]:
            distance = ((self.player.x() - item.x()) ** 2 +
                        (self.player.y() - item.y()) ** 2) ** 0.5
            if distance < ITEM_PICKUP_RANGE:
                self.collect_item(item)
                break

    def visit_tavern(self):
        """Посещение таверны для лечения"""
        gold_amount = self.get_gold_amount()
        if gold_amount >= TAVERN_PRICE:
            # Получение текущего здоровья из базы данных
            self.cursor.execute('SELECT health FROM players WHERE id = ?', (self.current_user[0],))
            current_health = self.cursor.fetchone()[0]

            if current_health < BASE_HEALTH:
                # Восстановление здоровья
                self.cursor.execute('UPDATE players SET health = ? WHERE id = ?', (BASE_HEALTH, self.current_user[0]))
                self.conn.commit()
                self.remove_item_from_inventory('gold', TAVERN_PRICE)

                # Обновление данных пользователя
                self.cursor.execute('SELECT * FROM players WHERE id = ?', (self.current_user[0],))
                self.current_user = self.cursor.fetchone()

                self.show_message('Таверна', f'Посещение таверны\nЗолото -{TAVERN_PRICE}')
                self.log_game_action('tavern', f'Посещение таверны за {TAVERN_PRICE} золота')
                self.show_main_menu()
            else:
                self.show_message('Таверна', 'В посещении таверны нет необходимости\nУ вас полное здоровье')
        else:
            self.show_message(
                'Таверна',
                f'У вас недостаточно золота для посещения таверны\nУ вас {gold_amount} золотых монет. Нужно - {TAVERN_PRICE}')

    def add_item_to_inventory(self, item_type, quantity):
        """Добавление предмета в инвентарь"""
        self.cursor.execute(
            'SELECT id, quantity FROM inventory WHERE player_id = ? AND item_type = ?',
            (self.current_user[0], item_type)
        )
        result = self.cursor.fetchone()
        if result:
            new_quantity = result[1] + quantity
            self.cursor.execute(
                'UPDATE inventory SET quantity = ? WHERE id = ?',
                (new_quantity, result[0])
            )
        else:
            self.cursor.execute(
                'INSERT INTO inventory (player_id, item_type, quantity) VALUES (?, ?, ?)',
                (self.current_user[0], item_type, quantity)
            )
        self.conn.commit()

    def remove_item_from_inventory(self, item_type, quantity):
        """Удаление предмета из инвентаря"""
        self.cursor.execute(
            'SELECT id, quantity FROM inventory WHERE player_id = ? AND item_type = ?',
            (self.current_user[0], item_type)
        )
        result = self.cursor.fetchone()
        if result:
            new_quantity = max(0, result[1] - quantity)
            if new_quantity > 0:
                self.cursor.execute(
                    'UPDATE inventory SET quantity = ? WHERE id = ?',
                    (new_quantity, result[0])
                )
            else:
                self.cursor.execute('DELETE FROM inventory WHERE id = ?', (result[0],))
            self.conn.commit()
            return True
        return False

    def get_gold_amount(self):
        """Получение количества золота"""
        self.cursor.execute(
            'SELECT quantity FROM inventory WHERE player_id = ? AND item_type = ?',
            (self.current_user[0], 'gold')
        )
        result = self.cursor.fetchone()
        return result[0] if result else 0

    def update_gold_display(self):
        """Обновление отображения золота"""
        gold_amount = self.get_gold_amount()
        self.gold_label.setText(f'Золото: {gold_amount}')

    def show_inventory(self):
        """Отображение инвентаря"""
        background_label = QLabel()
        background_label.setStyleSheet("background-color: #DEB887;")
        background_pixmap = QPixmap("Pictures/inventory_bg.png")
        background_pixmap = background_pixmap.scaled(WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio)
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout = QHBoxLayout()
        main_layout.addStretch()
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('🎒 ИНВЕНТАРЬ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #f39c12; background-color: rgba(210, 180, 140, 0.8); padding: 15px; border-radius: 10px;"
        )
        content_layout.addWidget(title)
        # Получение предметов из инвентаря
        self.cursor.execute(
            'SELECT item_type, quantity FROM inventory WHERE player_id = ? AND quantity > 0',
            (self.current_user[0],)
        )
        items = self.cursor.fetchall()
        # Создание таблицы для инвентаря
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(['Предмет', 'Количество'])
        table.setRowCount(len(items))
        table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(210, 180, 140, 0.5);
                color: #2c3e50;
                gridline-color: rgba(139, 69, 19, 0.5);
                border: 2px solid #8B4513;
            }
            QTableWidget::item {
                background-color: transparent;
                padding: 8px;
                color: #2c3e50;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: rgba(160, 120, 80, 0.6);
            }
            QHeaderView::section {
                background-color: #8B4513;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #A0522D;
                font-size: 12px;
            }
        """)
        # Отображение предметов
        item_names = {
            'gold': '💰 Золотые монеты',
            'weapon': '⚔️ Обломки оружия',
            'armor': '🛡️ Обломки брони',
            'health_potion': '❤️ Зелье здоровья',
            'mana_potion': '🔮 Зелье маны'
        }
        for i, (item_type, quantity) in enumerate(items):
            display_name = item_names.get(item_type, item_type)
            table.setItem(i, 0, QTableWidgetItem(display_name))
            table.setItem(i, 1, QTableWidgetItem(str(quantity)))
        table.resizeColumnsToContents()
        content_layout.addWidget(table)

        back_btn = QPushButton('Назад')
        back_btn.clicked.connect(self.show_main_menu)
        back_btn.setStyleSheet("background-color: #A0522D; color: white; font-weight: bold; padding: 10px;")
        content_layout.addWidget(back_btn)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        background_label.setLayout(main_layout)
        self.setCentralWidget(background_label)

    def show_player_stats(self):
        """Отображение характеристик"""
        background_label = QLabel()
        background_label.setStyleSheet("background-color: #BC8F8F;")
        background_pixmap = QPixmap("Pictures/stats_bg.png")
        background_pixmap = background_pixmap.scaled(WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio)
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout = QHBoxLayout()
        main_layout.addStretch()
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('📊 ХАРАКТЕРИСТИКИ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #3498db; background-color: rgba(188, 143, 143, 0.8); padding: 15px; border-radius: 10px;"
        )
        content_layout.addWidget(title)
        content_layout.addStretch()
        # Статистика персонажа
        gold_amount = self.get_gold_amount()
        stats = [
            f"👤 Имя: {self.current_user[1]}",
            f"⭐ Уровень: {self.current_user[3]}",
            f"📈 Опыт: {self.current_user[4]}",
            f"❤️ Здоровье: {self.current_user[5]}/{BASE_HEALTH}",
            f"🔮 Мана: {BASE_MANA}/{BASE_MANA}",
            f"⚔️ Сила атаки: {self.current_user[7]}",
            f"🛡️ Защита: {self.current_user[8]}",
            f"💰 Золото: {gold_amount}",
            f"📅 Дата создания: {self.current_user[9]}"
        ]

        for stat in stats:
            label = QLabel(stat)
            label.setFont(QFont('Arial', 12))
            label.setStyleSheet("padding: 8px; color: #2c3e50; font-weight: bold;")
            content_layout.addWidget(label)

        content_layout.addStretch()
        back_btn = QPushButton('Назад')
        back_btn.clicked.connect(self.show_main_menu)
        back_btn.setStyleSheet("background-color: #A0522D; color: white; font-weight: bold; padding: 10px;")
        content_layout.addWidget(back_btn)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        background_label.setLayout(main_layout)
        self.setCentralWidget(background_label)

    def show_achievements(self):
        """Отображение достижений"""
        background_label = QLabel()
        background_pixmap = QPixmap("Pictures/achievements_bg.png")
        background_label.setStyleSheet("background-color: #54A22A;")
        background_pixmap = background_pixmap.scaled(WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio)
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout = QHBoxLayout()
        main_layout.addStretch()
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('🏆 ДОСТИЖЕНИЯ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #f1c40f; background-color: rgba(0, 0, 0, 0); padding: 15px; border-radius: 10px;")
        content_layout.addWidget(title)
        # Получение достижений из базы данных
        self.cursor.execute(
            'SELECT achievement_name, achieved_date FROM achievements WHERE player_id = ?',
            (self.current_user[0],)
        )
        achievements = self.cursor.fetchall()
        if achievements:
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(['Достижение', 'Дата получения'])
            table.setRowCount(len(achievements))
            table.setStyleSheet("""
                QTableWidget {
                    background-color: rgba(210, 180, 140, 0.5);
                    color: #2c3e50;
                    gridline-color: rgba(139, 69, 19, 0.5);
                    border: 2px solid #8B4513;
                }
                QTableWidget::item {
                    background-color: transparent;
                    padding: 8px;
                    color: #2c3e50;
                    font-weight: bold;
                }
                QTableWidget::item:selected {
                    background-color: rgba(160, 120, 80, 0.6);
                }
                QHeaderView::section {
                    background-color: #8B4513;
                    color: white;
                    font-weight: bold;
                    padding: 10px;
                    border: 1px solid #A0522D;
                    font-size: 12px;
                }
            """)

            achievement_names = {
                'Новичок': '🥉 Новичок',
                'Опытный воин': '🥈 Опытный воин',
                'Мастер': '🥇 Мастер'
            }
            for i, (name, date) in enumerate(achievements):
                display_name = achievement_names.get(name, name)
                table.setItem(i, 0, QTableWidgetItem(display_name))
                table.setItem(i, 1, QTableWidgetItem(date))

            table.resizeColumnsToContents()
            content_layout.addWidget(table)
        else:
            no_achievements_label = QLabel('🎯 У вас пока нет достижений!\nПродолжайте играть чтобы их получить!')
            no_achievements_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_achievements_label.setFont(QFont('Arial', 14))
            no_achievements_label.setStyleSheet(
                "color: white; background-color: rgba(0,0,0,0.5); padding: 20px; border-radius: 10px;"
            )
            content_layout.addWidget(no_achievements_label)
        back_btn = QPushButton('Назад')
        back_btn.clicked.connect(self.show_main_menu)
        back_btn.setStyleSheet("background-color: rgba(231, 76, 60, 0.8); color: white;")
        content_layout.addWidget(back_btn)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        background_label.setLayout(main_layout)
        self.setCentralWidget(background_label)

    def show_game_history(self):
        """История игры"""
        background_label = QLabel()
        background_label.setStyleSheet("background-color: #D2B48C;")
        background_pixmap = QPixmap("Pictures/history_bg.png")
        background_pixmap = background_pixmap.scaled(WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatio)
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        main_layout = QHBoxLayout()
        main_layout.addStretch()
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('📖 ИСТОРИЯ ПРИКЛЮЧЕНИЙ')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #9b59b6; background-color: rgba(0,0,0,0.7); padding: 15px; border-radius: 10px;")
        content_layout.addWidget(title)
        # Получение истории из б.д.
        self.cursor.execute(
            'SELECT action_type, description, timestamp FROM game_history WHERE player_id = ? ORDER BY timestamp DESC LIMIT 50',
            (self.current_user[0],)
        )
        history = self.cursor.fetchall()

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(['Действие', 'Описание', 'Время'])
        table.setRowCount(len(history))
        table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(210, 180, 140, 0.5);
                color: #2c3e50;
                gridline-color: rgba(139, 69, 19, 0.5);
                border: 2px solid #8B4513;
            }
            QTableWidget::item {
                background-color: transparent;
                padding: 8px;
                color: #2c3e50;
                font-weight: bold;
            }
            QTableWidget::item:selected {
                background-color: rgba(160, 120, 80, 0.6);
            }
            QHeaderView::section {
                background-color: #8B4513;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: 1px solid #A0522D;
                font-size: 12px;
            }
        """)
        # Иконки для разных действий
        action_icons = {
            'login': '🔐',
            'register': '✨',
            'battle': '⚔️',
            'level_up': '⭐',
            'item_collect': '🎁',
            'shop': '🏪',
            'tavern': '🍺',
            'mine': '⛏️'
        }

        for i, (action_type, description, timestamp) in enumerate(history):
            icon = action_icons.get(action_type, '📝')
            table.setItem(i, 0, QTableWidgetItem(f"{icon} {action_type}"))
            table.setItem(i, 1, QTableWidgetItem(description))
            table.setItem(i, 2, QTableWidgetItem(timestamp))

        table.resizeColumnsToContents()
        content_layout.addWidget(table)

        back_btn = QPushButton('Назад')
        back_btn.clicked.connect(self.show_main_menu)
        back_btn.setStyleSheet("background-color: rgba(231, 76, 60, 0.8); color: white;")
        content_layout.addWidget(back_btn)

        main_layout.addLayout(content_layout)
        main_layout.addStretch()
        background_label.setLayout(main_layout)
        self.setCentralWidget(background_label)

    def check_achievements(self):
        """Проверка и выдача достижений"""
        achievements = [
            (1, 'Новичок', 'Достигнут 1 уровень'),
            (5, 'Опытный воин', 'Достигнут 5 уровень'),
            (10, 'Мастер', 'Достигнут 10 уровень')
        ]

        for level, name, description in achievements:
            if self.player.level >= level:
                self.cursor.execute(
                    'SELECT id FROM achievements WHERE player_id = ? AND achievement_name = ?',
                    (self.current_user[0], name)
                )
                if not self.cursor.fetchone():
                    self.cursor.execute(
                        'INSERT INTO achievements (player_id, achievement_name) VALUES (?, ?)',
                        (self.current_user[0], name)
                    )
                    self.conn.commit()
                    self.add_log(f"🎖 Получено достижение: {name}!")

    def log_game_action(self, action_type, description):
        """Запись действий игрока"""
        self.cursor.execute(
            'INSERT INTO game_history (player_id, action_type, description) VALUES (?, ?, ?)',
            (self.current_user[0], action_type, description)
        )
        self.conn.commit()

    def game_over(self):
        """Завершение игры"""
        self.game_timer.stop()
        self.enemy_spawn_timer.stop()
        # Проверка на нахождение в форме тени
        if self.player and hasattr(self.player, 'is_shadow_form') and self.player.is_shadow_form:
            self.player.end_shadow_form()
        # Сохранение прогресса
        if self.player and self.current_user:
            self.cursor.execute(
                'UPDATE players SET level = ?, exp = ?, health = ?, mana = ?, attack_power = ?, defense = ? WHERE id = ?',
                (self.player.level, self.player.exp, BASE_HEALTH,
                 self.player.mana, self.player.attack_power, self.player.defense, self.current_user[0])
            )
            self.conn.commit()

        self.show_message('Игра окончена', 'Ваш герой пал в бою!')
        self.show_main_menu()

    def closeEvent(self, event):
        """Закрытие приложения"""
        if self.current_user and self.player:
            self.save_player_progress()
        self.conn.close()
        event.accept()

    def show_mine(self):
        """Интерфейс шахты"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        background_label = QLabel()
        background_label.setStyleSheet("background-color: #1A191D;")
        background_pixmap = QPixmap("Pictures/mine_bg.png")
        background_pixmap = background_pixmap.scaled(
            WINDOW_WIDTH, WINDOW_HEIGHT, Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        background_label.setPixmap(background_pixmap)
        background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel('⛏️ ШАХТА')
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont('Arial', 20, QFont.Weight.Bold))
        title.setStyleSheet(
            "color: #f39c12; background-color: rgba(0,0,0,0.7); padding: 15px; border-radius: 10px;"
        )
        main_layout.addWidget(title)

        info_label = QLabel('Копайте в шахте с шансом найти золото')
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet(
            "color: white; background-color: rgba(0,0,0,0.5); padding: 10px; border-radius: 5px;"
        )
        main_layout.addWidget(info_label)
        main_layout.addStretch()
        # Кнопка для работы в шахте
        work_btn = QPushButton('⛏️\nКОПАТЬ')
        work_btn.setFont(QFont('Arial', 24, QFont.Weight.Bold))
        work_btn.setFixedSize(200, 200)
        work_btn.clicked.connect(self.work_in_mine)
        work_btn.setStyleSheet("""
            QPushButton {
                background-color: #e67e22; 
                color: white; 
                font-weight: bold;
                border: 4px solid #f39c12;
                border-radius: 20px;
                min-width: 200px;
                min-height: 200px;
                max-width: 200px;
                max-height: 200px;
            }
            QPushButton:hover {
                background-color: #f39c12;
                border: 4px solid #e67e22;
            }
            QPushButton:pressed {
                background-color: #d35400;
            }
        """)
        main_layout.addWidget(work_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addStretch()

        back_btn = QPushButton('Назад')
        back_btn.clicked.connect(self.show_main_menu)
        back_btn.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; padding: 10px;")
        main_layout.addWidget(back_btn)

        background_label.setLayout(main_layout)
        self.setCentralWidget(background_label)

    def work_in_mine(self):
        """Работа в шахте с шансом найти золото"""
        if random.random() < MINE_SUCCESS_CHANCE:  # 10% шанс
            gold_earned = 1
            self.add_item_to_inventory('gold', gold_earned)
            self.log_game_action('mine', f'Найдено {gold_earned} золота в шахте')

            self.show_message('🎉 Удача!', 'Вы нашли золотую монету!\n+1 золотая монета')
        else:
            self.log_game_action('mine', 'Попытка копать в шахте - ничего не найдено')

    # Вспомогательные методы
    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        """Показ сообщений"""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        if icon != QMessageBox.Icon.Information:
            msg_box.setIcon(icon)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setStyleSheet("QLabel{ color: #000000; }")
        msg_box.exec()

    def stop_game_timers(self):
        """Остановка таймеров"""
        if hasattr(self, 'game_timer') and self.game_timer.isActive():
            self.game_timer.stop()
        if hasattr(self, 'enemy_spawn_timer') and self.enemy_spawn_timer.isActive():
            self.enemy_spawn_timer.stop()

    def save_player_progress(self):
        """Сохранение прогресса"""
        self.cursor.execute(
            'UPDATE players SET level = ?, exp = ?, health = ?, mana = ?, attack_power = ?, defense = ? WHERE id = ?',
            (self.player.level, self.player.exp, self.player.health,
             self.player.mana, self.player.attack_power, self.player.defense, self.current_user[0])
        )
        self.conn.commit()

    def reset_game_state(self):
        """Сброс состояниябитвы"""
        self.player = None
        if hasattr(self, 'enemies'):
            self.enemies.clear()
        if hasattr(self, 'items'):
            self.items.clear()
        self.scene = None


class SkillDialog(QDialog):
    """Выбор навыков в бою"""
    def __init__(self, player, enemy, parent=None):
        super().__init__(parent)
        self.player = player
        self.enemy = enemy
        self.selected_skill = None
        self.unlocked_skills = self.get_unlocked_skills()
        self.initUI()

    def get_unlocked_skills(self):
        """Открытые игроком навыки"""
        if hasattr(self.player, 'game') and self.player.game.current_user:
            cursor = self.player.game.cursor
            cursor.execute(
                'SELECT skill_name FROM player_skills WHERE player_id = ? AND unlocked = TRUE',
                (self.player.game.current_user[0],)
            )
            skills = [row[0] for row in cursor.fetchall()]
        else:
            skills = []
        # Добавление базовых навыков
        base_skills = ['basic_attack', 'meditation']
        for skill in base_skills:
            if skill not in skills:
                skills.append(skills)
        return skills

    def initUI(self):
        """Подготовка интерфейса"""
        self.setWindowTitle('Выбор навыка')
        self.setGeometry(300, 300, 400, 300)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2c3e50, stop:1 #34495e);
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3498db, stop:1 #2980b9);
                border: 2px solid #1f618d;
                border-radius: 8px;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 10px;
                min-width: 120px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #5dade2, stop:1 #3498db);
            }
            QPushButton.escape {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e74c3c, stop:1 #c0392b);
            }
            QPushButton.escape:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ec7063, stop:1 #e74c3c);
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background-color: rgba(0,0,0,0.5);
                padding: 5px;
                border-radius: 5px;
            }
        """)

        layout = QVBoxLayout()
        # Информация о битве
        info_label = QLabel(f"БИТВА: {self.player.level} ур. vs {self.enemy.enemy_type} {self.enemy.level} ур.")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        layout.addWidget(info_label)

        hp_label = QLabel(f"Ваше HP: {self.player.health} | HP врага: {self.enemy.health}")
        hp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hp_label)

        mana_label = QLabel(f"Ваша мана: {self.player.mana}/100")
        mana_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mana_label)
        # Сетка навыков
        skills_grid = QGridLayout()
        row, col = 0, 0
        # Базовые навыки - первая строка
        attack_btn = QPushButton('⚔️ Базовая атака\n'
                                 f'Урон: {self.player.attack_power}\n'
                                 'Мана: 5')
        attack_btn.clicked.connect(lambda: self.select_skill('basic_attack'))
        skills_grid.addWidget(attack_btn, row, col)
        col += 1
        mana_btn = QPushButton('🔮 Медитация\n'
                               'Восстановление: 20 маны\n'
                               'Мана: 0')
        mana_btn.clicked.connect(lambda: self.select_skill('meditation'))
        skills_grid.addWidget(mana_btn, row, col)
        row, col = 1, 0
        # Сильная атака
        if 'strong_attack' in self.unlocked_skills:
            strong_attack_btn = QPushButton('💥 Сильная атака\n'
                                            f'Урон: {int(self.player.attack_power * STRONG_ATTACK_MULTIPLIER)}\n'
                                            'Мана: 15')
            strong_attack_btn.clicked.connect(lambda: self.select_skill('strong_attack'))
            skills_grid.addWidget(strong_attack_btn, row, col)
            col += 1
        # Небесный удар
        if 'heavenly_strike' in self.unlocked_skills:
            heavenly_btn = QPushButton('🎯 Небесный удар\n'
                                       f'Урон: {self.player.attack_power * HEAVENLY_STRIKE_MULTIPLIER}\n'
                                       'Мана: 25')
            heavenly_btn.clicked.connect(lambda: self.select_skill('heavenly_strike'))
            skills_grid.addWidget(heavenly_btn, row, col)
            col += 1
        # Третья строка - только Тень Забвения
        row, col = 2, 0
        # Навык Тени Забвения - всегда виден, но доступен только с нужного уровня
        shadow_btn = QPushButton('🌑 Тень Забвения\n'
                                 'Урон: ???\n'
                                 'Мана: ???')
        shadow_btn.clicked.connect(lambda: self.select_skill('shadow_oblivion'))
        skills_grid.addWidget(shadow_btn, row, col, 1, 2)
        layout.addLayout(skills_grid)
        # Кнопка побега
        escape_btn = QPushButton('🏃 Сбежать')
        escape_btn.setProperty('class', 'escape')
        escape_btn.clicked.connect(self.attempt_escape)
        layout.addWidget(escape_btn)
        self.setLayout(layout)

    def attempt_escape(self):
        """Попытка сбежать"""
        if random.random() < ESCAPE_CHANCE:  # 20% шанс
            self.selected_skill = 'escape_success'
            self.accept()
        else:
            self.selected_skill = 'escape_failed'
            self.accept()

    def select_skill(self, skill):
        """Выбор навыка"""
        self.selected_skill = skill
        self.accept()


class BattleSystem:
    """Пошаговых битвы"""
    def __init__(self, game):
        self.game = game
        self.is_battle_active = False
        self.current_enemy = None

    def start_battle(self, enemy):
        """Начало битвы с врагом"""
        if self.is_battle_active:
            return
        self.is_battle_active = True
        self.current_enemy = enemy
        self.stop_all_enemies_movement()
        self.show_skill_dialog()

    def end_battle(self):
        """Окончание битвы (вызывается при победе, побеге или завершении боя)"""
        # Завершаем форму тени если она активна
        if self.game.player.shadow_form:
            self.game.player.end_shadow_form()
        self.resume_all_enemies_movement()
        self.is_battle_active = False

    def stop_all_enemies_movement(self):
        """Остановка движения всех врагов во время битвы"""
        for enemy in self.game.enemies:
            if hasattr(enemy, 'move_timer') and enemy.move_timer.isActive():
                enemy.move_timer.stop()

    def resume_all_enemies_movement(self):
        """Возобновление движения врагов после битвы"""
        for enemy in self.game.enemies:
            if (hasattr(enemy, 'move_timer') and
                    not enemy.move_timer.isActive() and
                    enemy != self.current_enemy):
                enemy.move_timer.start(ENEMY_MOVE_INTERVAL)

    def show_skill_dialog(self):
        """Показ диалога выбора навыка"""
        dialog = SkillDialog(self.game.player, self.current_enemy, self.game)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_skill:
            if dialog.selected_skill in ['escape_success', 'escape_failed']:
                self.handle_escape_attempt(dialog.selected_skill)
            else:
                self.execute_player_turn(dialog.selected_skill)
        else:
            self.end_battle()

    def handle_escape_attempt(self, escape_result):
        """Обработка попытки побега"""
        if escape_result == 'escape_success':
            self.game.add_log("🏃 Вам удалось сбежать из битвы!")
            self.end_battle()
        else:
            self.game.add_log("🏃 Попытка сбежать не удалась! Враг атакует!")
            self.execute_enemy_turn()

    def execute_player_turn(self, skill):
        """Выполнение хода игрока"""
        mana_costs = {
            'basic_attack': 5,
            'strong_attack': 15,
            'heavenly_strike': 25,
            'meditation': 0,
            'shadow_oblivion': 0
        }
        mana_cost = mana_costs.get(skill, 0)
        # Проверка уровня для Тени Забвения
        if skill == 'shadow_oblivion' and self.game.player.level < LEVEL_FOR_SHADOW:
            self.game.add_log(f"Этот навык ждет своего часа...")
            self.show_skill_dialog()
            return
        if self.game.player.mana < mana_cost:
            self.game.add_log("Недостаточно маны для использования навыка!")
        else:
            # Расход маны (кроме медитации)
            if skill != 'meditation':
                self.game.player.mana -= mana_cost
                self.game.mana_bar.setValue(int(self.game.player.mana))
            # Выполнение выбранного навыка
            if skill == 'basic_attack':
                damage = self.game.player.attack_power
                self.current_enemy.health -= damage
                self.game.add_log(f"⚔️ Вы используете базовую атаку и наносите {damage} урона!")

            elif skill == 'strong_attack':
                damage = int(self.game.player.attack_power * STRONG_ATTACK_MULTIPLIER)
                self.current_enemy.health -= damage
                self.game.add_log(f"💥 Вы используете сильную атаку и наносите {damage} урона!")

            elif skill == 'heavenly_strike':
                if random.random() < HEAVENLY_STRIKE_CHANCE:  # 70% шанс успеха
                    damage = self.game.player.attack_power * HEAVENLY_STRIKE_MULTIPLIER
                    self.current_enemy.health -= damage
                    self.game.add_log(f"🎯 НЕБЕСНЫЙ УДАР!!! Нанесено {damage} урона!")
                else:
                    self.game.add_log("🎯 Небесный удар промахнулся!")

            elif skill == 'meditation':
                mana_restore = MEDITATION_RESTORE
                self.game.player.mana = min(100, self.game.player.mana + mana_restore)
                self.game.mana_bar.setValue(int(self.game.player.mana))
                self.game.add_log(f"🔮 Вы медитируете и восстанавливаете {mana_restore} маны!")
            elif skill == 'shadow_oblivion':
                if not self.game.player.shadow_form:
                    self.game.player.activate_shadow_form()
                    self.game.add_log("💀 Вы призываете Тень Забвения, восстанавливая свою былую мощь!")
                else:
                    self.game.add_log("Вы уже в форме Тени!")
                    # Проверка мгновенного убийства в форме тени
            if self.game.player.shadow_form and self.current_enemy.health <= 0:
                if self.game.player.shadow_attack(self.current_enemy):
                    self.game.add_log(f"☠️ Тень Забвения поглощает {self.current_enemy.enemy_type}!")
                    self.game.defeat_enemy(self.current_enemy)
                    self.end_battle()
                    return
            # Проверка победы над врагом
            if self.current_enemy.health <= 0:
                self.game.defeat_enemy(self.current_enemy)
                self.end_battle()
                return
        # Ход врага
        self.execute_enemy_turn()

    def execute_enemy_turn(self):
        """Выполнение хода врага"""
        if not self.current_enemy or self.current_enemy.health <= 0:
            self.end_battle()
            return
        # Атака врага
        enemy_damage = max(1, self.current_enemy.attack_power - self.game.player.defense // 2)
        self.game.player.health -= enemy_damage
        self.game.health_bar.setValue(int(self.game.player.health))
        self.game.add_log(f"{self.current_enemy.enemy_type} атакует и наносит {enemy_damage} урона!")
        # Проверка смерти игрока
        if self.game.player.health <= 0:
            self.game.player.health = 0
            self.end_battle()
            self.game.game_over()
            return
        self.show_skill_dialog()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    game = RPGGame()
    game.show()
    sys.exit(app.exec())