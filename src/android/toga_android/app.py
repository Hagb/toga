from toga.handlers import wrapped_handler
import ctypes
from .window import Window, TogaWin
from .libs.activity import IPythonApp, MainActivity
from rubicon.java import android_events
from rubicon import java
# `MainWindow` is defined here in `app.py`, not `window.py`, to mollify the test suite.


class MainWindow(Window):
    def show(self):
        pass


class TogaApp(IPythonApp):
    def __init__(self, app):
        super().__init__()
        MainActivity.setPythonApp(self)
        print('Python app launched & stored in Android Activity class')
        self.main_toga_win = None

    def getPythonWinById(self, obj):
        obj.setPythonWin(ctypes.cast(obj.getPythonWinId(), ctypes.py_object).value)

    @property
    def native(self):
        # We access `MainActivity.singletonThis` freshly each time, rather than
        # storing a reference in `__init__()`, because it's not safe to use the
        # same reference over time because `rubicon-java` creates a JNI local
        # reference.
        return MainActivity.singletonThis

    def getMainWinId(self, obj):
        print(id(self.main_toga_win))
        obj.setPythonWinId(id(self.main_toga_win))


class App:
    def __init__(self, interface):
        self.interface = interface
        self.interface._impl = self
        self._listener = None

        self.loop = android_events.AndroidEventLoop()

    @property
    def native(self):
        return self._listener.native if self._listener else None

    def create(self):
        # The `_listener` listens for activity event callbacks. For simplicity,
        # the app's `.native` is the listener's native Java class.
        self._listener = TogaApp(self)
        # Call user code to populate the main window
        self.interface.startup()

    def open_document(self, fileURL):
        print("Can't open document %s (yet)" % fileURL)

    def main_loop(self):
        # In order to support user asyncio code, start the Python/Android cooperative event loop.
        self.loop.run_forever_cooperatively()

        # On Android, Toga UI integrates automatically into the main Android event loop by virtue
        # of the Android Activity system.
        self.create()

    def set_main_window(self, window):
        self._listener.main_toga_win = TogaWin(window._impl)

    def show_about_dialog(self):
        self.interface.factory.not_implemented("App.show_about_dialog()")

    def exit(self):
        pass

    def set_on_exit(self, value):
        pass

    def add_background_task(self, handler):
        self.loop.call_soon(wrapped_handler(self, handler), self)
