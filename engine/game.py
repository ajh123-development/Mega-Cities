import sys

from .sprites import *
from .generators import *
from .camera import *
from .converter import *
from .economy import *
from .loaders.save_data_handler import *
from .loaders.plugn_handler import PluginLoader
from .loaders.tile_loader import TileFile, TileLookup
from .threads.WorkerThreads import WorkerThread
from .threads.DelayedFunctions import TimeoutFunction
from .threads.DelayedFunctions import TodoList
from .networking.Server import ServerMain
from .networking.Client import Client
from PodSixNet.Connection import connection
import time
import os


class Game:

    def __init__(self):
        """Initialize screen, pygame, map data, and settings."""
        pg.init()
        self.TileFile = TileFile()
        self.TileLookup = TileLookup(self.TileFile)

        self.server = ServerMain()
        self.client = Client(host="127.0.0.1", port=35565)

        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption(TITLE)
        self.dt = 0
        self.clock = pg.time.Clock()
        pg.key.set_repeat(500, 100)
        self.playing = True
        self.gen = Generate()
        self.iso = Converter()
        self.interval = INTERVAL
        self.ticks = 0

        self.gamestate = {}
        self.economy = Economy(STARTINGMONEY)
        self.all_sprites = pg.sprite.Group()
        self.tiles = pg.sprite.Group()
        self.grid_background = Grid(self, W, H)
        self.grid_background.create_grid(1)
        self.grid_foreground = Grid(self, W, H)
        self.grid_foreground.create_grid(0)
        self.player = Player(self, 2, 2)
        self.player_pos = {"x": 0, "y": 0}
        self.camera = Camera(self.grid_background.width, self.grid_background.height)
        self.threads = []
        self.run_later = TodoList()

        plugins = []
        s_dir = os.getcwd()+"/plugins"
        for file in os.listdir(s_dir):
            if file.endswith(".py"):
                mod_name = file[:-3]  # strip .py at the end
                plugins.append("."+mod_name)

        self.PluginLoader = PluginLoader(self, plugins)

    def _run_thread(self):
        """Method that runs forever."""
        self.ticks += INTERVAL
        self.run_later.execute_ready_functions()
        self.animate()
        self.PluginLoader.run()


    def _net_thread(self):
        """Method that runs network forever."""
        self.server.Pump()
        connection.Pump()
        self.client.Pump()

    def new(self):
        """Initialize all variables and do all the setup for a new game."""
        self.server.Pump()
        self.client.Pump()
        self.client.Send({"action": "myaction", "blah": 123, "things": [3, 4, 3, 4, 7]})

    def run(self):
        """Game loop."""
        while self.playing:
            self.dt = self.clock.tick(FPS) / 1000
            self._net_thread()
            self._run_thread()
            # Catch all events.
            self.events()
            # Update data.
            self.update()
            # Draw updated screen.
            self.draw()

    def quit(self):
        """Quit the game."""
        pg.quit()
        sys.exit()

    def update(self):
        # Update everything here.
        self.grid_background.check_update_grid()
        self.grid_foreground.check_update_grid()
        self.all_sprites.update()
        self.camera.update(self.player)

        for thread_index in range(0, len(self.threads)):
            if self.threads[thread_index] is not None and self.threads[thread_index].stop:
                self.threads[thread_index] = None

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

                    # Stop these threads
                    for thread in self.threads:
                        if thread is not None:
                            thread.stop = True

                    self.server.close()
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
                    self.change_tile(self.TileLookup.lookup_from_title("concrete"))
                if event.key == pg.K_1:
                    self.change_tile(self.TileLookup.lookup_from_title("grass_west"))
                if event.key == pg.K_SPACE:
                    self.transform_tile()

    def transform_tile(self):
        x, y = self.player.current_position()
        if isinstance(self.grid_background.grid_data[x][y].data, int):
            self._dirt_transform(x, y)
        elif self.grid_background.grid_data[x][y].data == 1:
            self._dirt_transform(x, y)
        else:
            print(f'''You can't grow a crop on {self.grid_background.grid_data[x][y].tile_string}!''')

    def change_tile(self, data):
        x, y = self.player.current_position()
        tile_title = self.TileFile.titles[data]
        back_title = self.grid_background.grid_data[x][y].tile_string
        if self.grid_background.grid_data[x][y].data != data:
            if self.economy.check_transaction(tile_title):
                self.grid_background.update_tile(data, x, y)
                self.grid_background.check_update_grid()
                self.economy.buy(tile_title)
        else:
            print(f'''You can't place {tile_title} on a {back_title}!''')

    def _dirt_transform(self, x, y):
        if self.grid_foreground.grid_data[x][y].data >= self.TileLookup.lookup_from_title("orange tulip:flower"):
            self.economy.sell(self.grid_foreground.grid_data[x][y].tile_string)
            self.grid_foreground.update_tile(self.TileLookup.lookup_from_title("dirt"), x, y)
            self.grid_foreground.grid_data[x][y].multi_states = False
            self.grid_background.update_tile(self.TileLookup.lookup_from_title("dirt"), x, y)
        elif self.grid_background.grid_data[x][y].data == self.TileLookup.lookup_from_title("dirt"):
            self.grid_foreground.update_tile(self.TileLookup.lookup_from_title("orange tulip:seed"), x, y)
            self.grid_foreground.check_update_grid()
            self.grid_foreground.grid_data[x][y].multi_states = True
            self.economy.buy(self.grid_foreground.grid_data[x][y].tile_string)
        else:
            self.grid_background.update_tile(self.TileLookup.lookup_from_title("dirt"), x, y)

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
        self.new()

    def animate(self):
        for row_nb, row in enumerate(self.grid_foreground.grid_data):
            for col_nb, tile in enumerate(row):
                self.display_next_state(tile, self.grid_foreground, row_nb, col_nb)

        for row_nb, row in enumerate(self.grid_background.grid_data):
            for col_nb, tile in enumerate(row):
                self.display_next_state(tile, self.grid_background, row_nb, col_nb)

    def display_next_state(self, tile: Tile, grid: Grid, row_nb, col_nb):
        if tile.data != 0:
            net_name = self.TileLookup.lookup_from_int(tile.data)
            if tile.multi_states:
                states = self.TileLookup.lookup_tile_states(net_name)
                last = list(states)[-1]
                do_loop = self.TileFile.loop[tile.data]
                result = self.gen.generate_random_number(0, 1)
                multiplier = self.TileFile.tick_multiplier[tile.data]

                def actually_display():
                    string_data = str(tile.data)
                    split_string = string_data.split(".", 1)
                    dec = int(split_string[1])+1
                    new_data = float(split_string[0]+"."+str(dec))

                    if new_data <= last:
                        if result == 0:
                            if do_loop:
                                new_data = self.TileLookup.lookup_from_title(states[0])

                            grid.update_tile(new_data, row_nb, col_nb)

                func = TimeoutFunction(actually_display, self.ticks * multiplier)
                self.run_later.add_to_list(func)
