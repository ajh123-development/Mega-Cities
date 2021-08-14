import sys

from .sprites import *
from .generators import *
from .camera import *
from .converter import *
from .economy import *
from .loaders.save_data_handler import *
from .loaders.plugn_handler import PluginLoader
from .loaders.tile_loader import TileFile
import threading
import time
import os


class Game:

    def __init__(self):
        """Initialize screen, pygame, map data, and settings."""
        pg.init()
        self.TileFile = TileFile()

        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.dt = 0
        self.clock = pg.time.Clock()
        pg.key.set_repeat(500, 100)
        self.playing = True
        self.gen = Generate()
        self.iso = Converter()
        self.interval = INTERVAL

        self.gamestate = {}
        self.economy = Economy(STARTINGMONEY)
        self.all_sprites = pg.sprite.Group()
        self.tiles = pg.sprite.Group()
        self.grid_background = Grid(self, W, H)
        self.grid_background.create_grid('b')
        self.grid_foreground = Grid(self, W, H)
        self.grid_foreground.create_grid(0)
        self.player = Player(self, 2, 2)
        self.player_pos = {"x": 0, "y": 0}
        self.camera = Camera(self.grid_background.width, self.grid_background.height)

        plugins = []
        s_dir = os.getcwd()+"/plugins"
        for file in os.listdir(s_dir):
            if file.endswith(".py"):
                mod_name = file[:-3]  # strip .py at the end
                plugins.append("."+mod_name)

        self.PluginLoader = PluginLoader(self, plugins)

    def _run_thread(self):
        """Method that runs forever."""
        while True:
            self.grow()
            self.PluginLoader.run()
            time.sleep(self.interval)

    def new(self):
        """Initialize all variables and do all the setup for a new game."""

        thread = threading.Thread(target=self._run_thread, args=())
        thread.start()  # Start the execution

    def run(self):
        """Game loop."""
        while self.playing:
            self.dt = self.clock.tick(FPS) / 1000
            # Catch all events.
            self.events()
            # Update data.
            self.update()
            # Draw updated screen.
            self.draw()

    @staticmethod
    def quit():
        """Quit the game."""
        pg.quit()
        sys.exit()

    def update(self):
        # Update everything here.
        self.grid_background.check_update_grid()
        self.grid_foreground.check_update_grid()
        self.all_sprites.update()
        self.camera.update(self.player)

    def draw(self):
        """Draw the screen."""
        self.screen.fill(BGCOLOR)
        for tile in self.tiles:
            self.screen.blit(tile.image, self.camera.apply(tile))
        for sprite in self.all_sprites:
            self.screen.blit(sprite.image, self.camera.apply(sprite))
        pg.display.flip()

    def events(self):
        """Catch all events here."""
        for event in pg.event.get():
            if event.type == pg.QUIT:
                self.quit()
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_ESCAPE:
                    self.save_gamestate()
                    self.playing = False
                if event.key == pg.K_LEFT:
                    self.player.move(dx=-1)
                if event.key == pg.K_RIGHT:
                    self.player.move(dx=1)
                if event.key == pg.K_UP:
                    self.player.move(dy=-1)
                if event.key == pg.K_DOWN:
                    self.player.move(dy=1)
                if event.key == pg.K_RETURN:
                    self.change_tile('a')
                if event.key == pg.K_SPACE:
                    self.transform_tile()

    def transform_tile(self):
        x, y = self.player.current_position()
        if isinstance(self.grid_background.grid_data[x][y].data, int):
            self._dirt_transform(x, y)
        elif self.grid_background.grid_data[x][y].data == 'b':
            self._dirt_transform(x, y)
        else:
            print(f'''You can't grow a crop on {self.grid_background.grid_data[x][y].tile_string}!''')

    def change_tile(self, data):
        x, y = self.player.current_position()
        if isinstance(self.grid_background.grid_data[x][y].data, str):
            if self.economy.check_transaction('concrete'):
                self.grid_background.update_tile(data, x, y)
                self.grid_background.check_update_grid()
                self.economy.buy(self.grid_background.grid_data[x][y].tile_string)
        else:
            print(f'''You can't place concrete on a crop!''')

    def _dirt_transform(self, x, y):
        if self.grid_foreground.grid_data[x][y].data >= 5:
            self.economy.sell(self.grid_foreground.grid_data[x][y].tile_string)
            self.grid_foreground.update_tile(2, x, y)
            self.grid_foreground.grid_data[x][y].multi_states = False
            self.grid_background.update_tile(2, x, y)
        elif self.grid_background.grid_data[x][y].data == 2:
            self.grid_foreground.update_tile(3, x, y)
            self.grid_foreground.check_update_grid()
            self.grid_foreground.grid_data[x][y].multi_states = True
            self.economy.buy(self.grid_foreground.grid_data[x][y].tile_string)
        else:
            self.grid_background.update_tile(2, x, y)

    def save_gamestate(self):
        self.grid_background.check_update_grid()
        self.grid_foreground.check_update_grid()
        d = Data('save_data.txt')
        maps_dict = {'maps':
                     {'background': self.grid_background.grid_list(),
                      'foreground': self.grid_foreground.grid_list()
                      }}
        player_dict = {'position':
                       {'x': self.player.x,
                        'y': self.player.y
                        }}
        economy_dict = {'money': self.economy.money}
        d.update_file('game state', maps_dict)
        d.update_file('economy', economy_dict)
        d.update_file('player', player_dict)
        d.save_to_file()

    def load_gamestate(self):
        self.player.kill()
        d = Data('save_data.txt')
        self.gamestate = d.load_master_dict('game state')
        background_list = self.gamestate['maps']['background']
        foreground_list = self.gamestate['maps']['foreground']
        economy = d.load_master_dict('economy')
        player_data = d.load_master_dict('player')
        money = economy['money']
        self.player_pos = player_data['position']
        return money, background_list, foreground_list

    def load(self):
        self.all_sprites = pg.sprite.Group()
        self.tiles = pg.sprite.Group()
        money, background_list, foreground_list = self.load_gamestate()
        self.economy = Economy(money)
        self.grid_background = Grid(self, len(background_list), len(background_list[0]))
        self.grid_background.load_grid(background_list)
        self.grid_foreground = Grid(self, len(foreground_list), len(foreground_list[0]))
        self.grid_foreground.load_grid(foreground_list)
        self.player = Player(self, self.player_pos['x'], self.player_pos['y'])
        self.camera = Camera(self.grid_background.width, self.grid_background.height)
        thread = threading.Thread(target=self._run_thread, args=())
        thread.start()

    def grow(self):
        for row_nb, row in enumerate(self.grid_foreground.grid_data):
            for col_nb, tile in enumerate(row):
                if tile.multi_states:
                    result = self.gen.generate_random_number(0, 1)
                    if result == 0:
                        tile.data += 1
                        self.grid_foreground.update_tile(tile.data, row_nb, col_nb)
