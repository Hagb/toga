import asyncio
import toga
from .libs.activity import IPythonWin, WinActivity, MainActivity
from .libs.android.content import Intent
from .libs.android.view import Menu, MenuItem
from .libs.android.graphics import Drawable
from toga.command import Group

from . import dialogs
from .libs.android import R__attr
from .libs.android.util import TypedValue

from rubicon.java.jni import java


class AndroidViewport:
    def get_content(self):
        return self.native.getContext()

    def __init__(self, native):
        self.native = native
        self.dpi = self.get_content().getResources().getDisplayMetrics().densityDpi
        # Toga needs to know how the current DPI compares to the platform default,
        # which is 160: https://developer.android.com/training/multiscreen/screendensities
        self.baseline_dpi = 160
        self.scale = float(self.dpi) / self.baseline_dpi

    @property
    def width(self):
        return self.get_content().getResources().getDisplayMetrics().widthPixels

    @property
    def height(self):
        screen_height = self.get_content().getResources().getDisplayMetrics().heightPixels
        return screen_height - self._status_bar_height() - self._action_bar_height()

    def _action_bar_height(self):
        """
        Get the size of the action bar. The action bar shows the app name and can provide some app actions.
        """
        tv = TypedValue()
        has_action_bar_size = self.get_content().getTheme(
        ).resolveAttribute(R__attr.actionBarSize, tv, True)
        if not has_action_bar_size:
            return 0

        return TypedValue.complexToDimensionPixelSize(
            tv.data, self.get_content().getResources().getDisplayMetrics())

    def _status_bar_height(self):
        """
        Get the size of the status bar. The status bar is typically rendered above the app,
        showing the current time, battery level, etc.
        """
        resource_id = self.get_content().getResources().getIdentifier(
            "status_bar_height", "dimen", "android")
        if resource_id <= 0:
            return 0

        return self.get_content().getResources().getDimensionPixelSize(resource_id)


class ApplicationAndroidViewport(AndroidViewport):
    def get_content(self):
        return self.native.getApplicationContext()


class TogaWin(IPythonWin):
    def __init__(self, window):
        super().__init__()
        # always increment before using it for invoking new Intents
        self.last_intent_requestcode = -1
        self.running_intents = {}          # dictionary for currently running Intents
        self.menuitem_mapping = {}         # dictionary for mapping menuitems to commands
        self.window = window
        self.window._listener = self
        self._impl = window

    def setNative(self, winActivity):
        self.window.native = WinActivity(
            __jni__=java.NewGlobalRef(winActivity))

    def onCreate(self):
        print("Toga app: onCreate")
        print("infooo:", self.window, id(self.window))
        self.window.widget.create_recursion(self.window.native)
        # Set the widget's viewport to be based on the window's content.
        self.window.widget.viewport = AndroidViewport(
            self.window.widget.native)
        # self.window.interface.content.refresh()

        # Attach child widgets to widget as their container.
        for child in self.window.widget.interface.children:
            child._impl.container = self.window.widget
            child._impl.viewport = self.window.widget.viewport
        self.window.widget.replay_recursion()
        self.window._set_title()
        self.window.interface.content.refresh()
        self.window.native.setContentView(self.window.widget.native)

    def onStart(self):
        print("Toga app: onStart")

    def onResume(self):
        print("Toga app: onResume")

    def onPause(self):
        print("Toga app: onPause")

    def onStop(self):
        print("Toga app: onStop")

    def onDestroy(self):
        print("Toga app: onDestroy")

    def onRestart(self):
        print("Toga app: onRestart")

    def onActivityResult(self, requestCode, resultCode, resultData):
        """
        Callback method, called from MainActivity when an Intent ends

        :param int requestCode: The integer request code originally supplied to startActivityForResult(),
                                allowing you to identify who this result came from.
        :param int resultCode: The integer result code returned by the child activity through its setResult().
        :param Intent resultData: An Intent, which can return result data to the caller (various data can be attached
                                  to Intent "extras").
        """
        print("Toga app: onActivityResult, requestCode={0}, resultData={1}".format(
            requestCode, resultData))
        try:
            # remove Intent from the list of running Intents,
            # and set the result of the intent.
            result_future = self.running_intents.pop(requestCode)
            result_future.set_result(
                {"resultCode": resultCode, "resultData": resultData})
        except KeyError:
            print("No intent matching request code {requestCode}")

    def onOptionsItemSelected(self, menuitem):
        consumed = False
        try:
            cmd = self.menuitem_mapping[menuitem.getItemId()]
            consumed = True
            if cmd.action is not None:
                cmd.action(menuitem)
        except KeyError:
            print("menu item id not found in menuitem_mapping dictionary!")
        return consumed

    def onPrepareOptionsMenu(self, menu):
        menu.clear()
        itemid = 0
        menulist = {}  # dictionary with all menus
        self.menuitem_mapping.clear()

        # create option menu
        for cmd in self.window.app.interface.commands:
            if cmd == toga.SECTION_BREAK or cmd == toga.GROUP_BREAK:
                continue
            if cmd in self.window.interface.toolbar:
                # do not show toolbar commands in the option menu (except when overflowing)
                continue

            grouppath = cmd.group.path
            if grouppath[0] != Group.COMMANDS:
                # only the Commands group (and its subgroups) are supported
                # other groups should eventually go into the navigation drawer
                continue
            if cmd.group.key in menulist:
                menugroup = menulist[cmd.group.key]
            else:
                # create all missing submenus
                parentmenu = menu
                for group in grouppath:
                    groupkey = group.key
                    if groupkey in menulist:
                        menugroup = menulist[groupkey]
                    else:
                        if group.label == toga.Group.COMMANDS.label:
                            menulist[groupkey] = menu
                            menugroup = menu
                        else:
                            itemid += 1
                            order = Menu.NONE if group.order is None else group.order
                            menugroup = parentmenu.addSubMenu(Menu.NONE, itemid, order,
                                                              group.label)  # groupId, itemId, order, title
                            menulist[groupkey] = menugroup
                    parentmenu = menugroup
            # create menu item
            itemid += 1
            order = Menu.NONE if cmd.order is None else cmd.order
            # groupId, itemId, order, title
            menuitem = menugroup.add(Menu.NONE, itemid, order, cmd.label)
            menuitem.setShowAsActionFlags(MenuItem.SHOW_AS_ACTION_NEVER)
            menuitem.setEnabled(cmd.enabled)
            # store itemid for use in onOptionsItemSelected
            self.menuitem_mapping[itemid] = cmd

        # create toolbar actions
        for cmd in self._impl.interface.toolbar:
            if cmd == toga.SECTION_BREAK or cmd == toga.GROUP_BREAK:
                continue
            itemid += 1
            order = Menu.NONE if cmd.order is None else cmd.order
            # groupId, itemId, order, title
            menuitem = menu.add(Menu.NONE, itemid, order, cmd.label)
            menuitem.setShowAsActionFlags(
                MenuItem.SHOW_AS_ACTION_IF_ROOM)  # toolbar button / item in options menu on overflow
            menuitem.setEnabled(cmd.enabled)
            if cmd.icon:
                icon = Drawable.createFromPath(str(cmd.icon._impl.path))
                if icon:
                    menuitem.setIcon(icon)
                else:
                    print('Could not create icon: ' + str(cmd.icon._impl.path))
            # store itemid for use in onOptionsItemSelected
            self.menuitem_mapping[itemid] = cmd

        return True


class Window:
    def __init__(self, interface):
        self.interface = interface
        self.interface._impl = self
        self.native = None
        self._title = None
        self.create()

    def create(self):
        pass

    def close(self):
        if self.native:
            self.native.finish()

    def set_app(self, app):
        self.app = app

    def set_content(self, widget):
        self.widget = widget
        print("infooo:", self, id(self), self.widget)
        if self.widget.native is None:
            self.widget.viewport = ApplicationAndroidViewport(
                MainActivity.singletonThis)

    def set_title(self, title):
        self._title = title
        if self.native:
            self._set_title()

    def _set_title(self):
        self.native.setTitle(self._title)

    def set_position(self, position):
        pass

    def set_size(self, size):
        pass

    def create_toolbar(self):
        pass

    def show(self):
        # self.app.native.
        if self.native is None:
            self.app.native.newActivity(id(TogaWin(self)))

    def set_full_screen(self, is_full_screen):
        self.interface.factory.not_implemented('Window.set_full_screen()')

    def info_dialog(self, title, message):
        dialogs.info(self, title, message)

    def question_dialog(self, title, message):
        self.interface.factory.not_implemented('Window.question_dialog()')

    def confirm_dialog(self, title, message):
        self.interface.factory.not_implemented('Window.confirm_dialog()')

    def error_dialog(self, title, message):
        self.interface.factory.not_implemented('Window.error_dialog()')

    def stack_trace_dialog(self, title, message, content, retry=False):
        self.interface.factory.not_implemented('Window.stack_trace_dialog()')

    def save_file_dialog(self, title, suggested_filename, file_types):
        self.interface.factory.not_implemented('Window.save_file_dialog()')

    # @property
    # def content(self):
    #     pass

    # @content.setter
    # def content(self, widget):
    #     if self.native is None:
    #         self.content
    #         # Assign the content widget to the same app as the window.
    #         widget.app = self.app
    #         # Assign the content widget to the window.
    #         widget.window = self
    #         # Track our new content
    #         self._content = widget
    #     else:
    #         super().content = widget

    async def intent_result(self, intent):
        """
        Calls an Intent and waits for its result.

        A RuntimeError will be raised when the Intent cannot be invoked.

        :param Intent intent: The Intent to call
        :returns: A Dictionary containing "resultCode" (int) and "resultData" (Intent or None)
        :rtype: dict
        """
        if intent.resolveActivity(self.native.getPackageManager()) is None:
            raise RuntimeError(
                'No appropriate Activity found to handle this intent.')
        self._listener.last_intent_requestcode += 1
        code = self._listener.last_intent_requestcode

        result_future = asyncio.Future()
        self._listener.running_intents[code] = result_future

        self.native.startActivityForResult(intent, code)
        await result_future
        return result_future.result()
