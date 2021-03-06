#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Deepin Technology Co., Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

import os
import time
import tempfile
import subprocess
from weakref import ref
from os.path import dirname

from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import qApp, QFileDialog
from PyQt5.QtCore import QStandardPaths, QUrl, QObject, QVariant
from PyQt5.QtCore import QRect, QPoint, QSize, QTimer, pyqtSignal

from i18n import _
from app_window import Window
from window_info import WindowInfo
from menu_controller import MenuController
from dbus_interfaces import controlCenterInterface
from dbus_interfaces import notificationsInterface
from dbus_interfaces import FileManagerInterface
from constants import MAIN_QML, GTK_CLIP

def validFormat(suffixname):
    pictureformat = [".bmp",".jpg",".jpeg",".png",".pbm",".pgm",".ppm",".xbm",".xpm"]
    return suffixname in pictureformat

class AppContext(QObject):
    """Every AppContext instance keeps an environment which is different
       from other instances, acting like a container.
    """

    needSound = pyqtSignal()
    needOSD = pyqtSignal(QRect)
    finished = pyqtSignal()

    def __init__(self, argValues):
        super(AppContext, self).__init__()
        self.argValues = argValues
        self.settings = None
        self.windowInfo = None
        self.window = None
        self.pixmap = None

        self._fileSaveLocation = None

    def _notify(self, *args, **kwargs):
        noNotificationValue = self.argValues["noNotification"]
        if noNotificationValue:
            self.finished.emit()
        else:
            return notificationsInterface.notify(_("Deepin Screenshot"),
                                                 *args, **kwargs)

    def _constructNotifyHints(self, path):
        if os.path.exists("/usr/bin/dde-file-manager"):
            encode = lambda x : QUrl.fromLocalFile(x).toString()
            argDict = {
                "directory" : encode(dirname(path)),
                "item" : encode(path)
            }
            arg = "{directory}?selectUrl={item}".format(**argDict)
            command = "dde-file-manager,%s" % arg
        else:
            command = "xdg-open,%s" % path


        hints = {
            "x-deepin-action-view": command
        }

        return hints

    def _windowVisibleChanged(self, visible):
        if visible:
            self.sender().disable_zone()
            self.sender().grabFocus()

            controlCenterInterface.hideImmediately()
        else:
            self.sender().enable_zone()
            self.sender().ungrabFocus()

            if self.settings.showOSD:
                area = QRect(QPoint(self.window.x(), self.window.y()),
                             QSize(self.window.width(), self.window.height()))
                self.needOSD.emit(area)

    # this function just handles the situation that this context's
    # finished by the user interaction.
    def _windowClosing(self):
        if self.settings.showOSD:
            area = QRect(QPoint(self.window.x(), self.window.y()),
                         QSize(self.window.width(), self.window.height()))
            self.needOSD.emit(area)
        self.finished.emit()

    def isActive(self):
        return self.window.isVisible()

    def copyPixmap(self, pixmap):
        _temp = "%s.png" % tempfile.mktemp()
        pixmap.save(_temp)
        subprocess.call([GTK_CLIP, _temp])

        self._notify(_("Picture has been saved to clipboard"))

    def savePixmap(self, pixmap, fileName):
        pixmap.save(fileName)

        self._fileSaveLocation = fileName

    def saveScreenshot(self, pixmap):
        self.needSound.emit()

        savePathValue = self.argValues["savePath"]
        timeStamp = time.strftime("%Y%m%d%H%M%S", time.localtime())
        fileName = "%s%s.png" % (_("DeepinScreenshot"), timeStamp)
        save_op = self.settings.getOption("save", "save_op")
        save_op_index = int(save_op)

        absSavePath = ""
        copyToClipborad = False
        if savePathValue != "":
            pic_dir = os.path.dirname(savePathValue)
            pic_name = os.path.basename(savePathValue)
            if pic_name == "":
                pic_name = fileName;
            else:
                pic_name_stuffix = os.path.splitext(pic_name)[1]
                if not validFormat(pic_name_stuffix):
                    pic_name = pic_name + ".png"
                    savePathValue = pic_dir + "/" + pic_name
            savePathValue = os.path.abspath(savePathValue)
        else:
            if save_op_index == 0: #saveId == "save_to_desktop":
                saveDir = QStandardPaths.writableLocation(
                    QStandardPaths.DesktopLocation)
                absSavePath = os.path.join(saveDir, fileName)
            elif save_op_index == 1: #saveId == "auto_save" :
                saveDir = QStandardPaths.writableLocation(
                    QStandardPaths.PicturesLocation)
                absSavePath = os.path.join(saveDir, fileName)
            elif save_op_index == 2: #saveId == "save_to_dir":
                lastSavePath = self.settings.getOption("save", "folder")
                absSavePath = QFileDialog.getSaveFileName(None, _("Save"),
                    os.path.join(lastSavePath, fileName))[0]
                if absSavePath != "":
                    pic_dir = os.path.dirname(absSavePath)
                    pic_name = os.path.basename(absSavePath)
                    if pic_name == "":
                        pic_name = fileName;
                    else:
                        pic_name_stuffix = os.path.splitext(pic_name)[1]
                        if not validFormat(pic_name_stuffix):
                            pic_name = pic_name + ".png"
                            absSavePath = pic_dir + "/" + pic_name
                self.settings.setOption("save", "folder",
                    os.path.dirname(absSavePath) or lastSavePath)
            elif save_op_index == 4: #saveId == "auto_save_ClipBoard":
                copyToClipborad = True
                saveDir = QStandardPaths.writableLocation(
                    QStandardPaths.PicturesLocation)
                absSavePath = os.path.join(saveDir, fileName)
            else: copyToClipborad = True

        actions = ["view", _("View")]
        if savePathValue:
            self.savePixmap(pixmap, savePathValue)

            hints = self._constructNotifyHints(savePathValue)
            self._notify(_("Picture has been saved to %s") % savePathValue,
                         actions, hints)
        elif absSavePath or copyToClipborad:
            if copyToClipborad:
                self.copyPixmap(pixmap)
            if absSavePath:
                copyToClipborad = False
                self.savePixmap(pixmap, absSavePath)

                hints = self._constructNotifyHints(absSavePath)
                self._notify(_("Picture has been saved to %s") % absSavePath,
                             actions, hints)

        self.finished.emit()

    def helpManual(self):
        subprocess.Popen(["dman", "deepin-screenshot"])
        self.finished.emit()

    def main(self):
        fullscreenValue = self.argValues["fullscreen"]
        topWindowValue = self.argValues["topWindow"]
        startFromDesktopValue = self.argValues["startFromDesktop"]
        savePathValue = self.argValues["savePath"]
        noNotificationValue = self.argValues["noNotification"]

        cursor_pos = QCursor.pos()
        desktop = qApp.desktop()
        screen_num = desktop.screenNumber(cursor_pos)
        screen_geo = desktop.screenGeometry(screen_num)
        pixmap = qApp.primaryScreen().grabWindow(0)
        pixmap = pixmap.copy(screen_geo.x(), screen_geo.y(),
                             screen_geo.width(), screen_geo.height())
        pixmap.save(self.settings.tmpImageFile)

        show_osd = self.settings.getOption("showOSD", "show")
        if show_osd == True or show_osd == "true":
            self.settings.showOSD = startFromDesktopValue
            if self.settings.showOSD:
                self.settings.setOption("showOSD", "show", QVariant(False))
        else:
            self.settings.showOSD = False
        self.menu_controller = MenuController()
        self.windowInfo = WindowInfo(screen_num)

        self.pixmap = pixmap
        self.window = Window(ref(self)())

        if fullscreenValue:
            self.saveScreenshot(pixmap)
        elif topWindowValue:
            wInfo = self.windowInfo.get_active_window_info()
            pix = pixmap.copy(wInfo[0], wInfo[1], wInfo[2], wInfo[3])
            self.saveScreenshot(pix)
        else:
            self.window.setX(screen_geo.x())
            self.window.setY(screen_geo.y())
            self.window.setWidth(screen_geo.width())
            self.window.setHeight(screen_geo.height())
            self.window.windowClosing.connect(self._windowClosing)
            self.window.visibleChanged.connect(self._windowVisibleChanged)

            # NOTE: make sure that all the objects that are set as context
            # property are always referenced by others through the lifetime
            # of this application, otherwise it'll cause problems.
            qml_context = self.window.rootContext()
            qml_context.setContextProperty("windowView", self.window)
            qml_context.setContextProperty("qApp", qApp)
            qml_context.setContextProperty("screenWidth",
                self.window.window_info.screen_width)
            qml_context.setContextProperty("screenHeight",
                self.window.window_info.screen_height)
            qml_context.setContextProperty("tmpImageFile",
                self.settings.tmpImageFile)
            qml_context.setContextProperty("blurImageFile",
                self.settings.tmpBlurFile)
            qml_context.setContextProperty("mosaicImageFile",
                self.settings.tmpMosaiceFile)
            qml_context.setContextProperty("_menu_controller",
                self.menu_controller)

            self.window.setSource(QUrl.fromLocalFile(MAIN_QML))
            self.window.showWindow()
            rootObject = self.window.rootObject()
            rootObject.helpView.connect(self.helpManual)
            rootObject.setProperty("saveSpecifiedPath", savePathValue)

            self.menu_controller.preMenuShow.connect(self.window.ungrabFocus)
            self.menu_controller.postMenuHide.connect(self.window.grabFocus)
