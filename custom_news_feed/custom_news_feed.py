# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CustomNewsFeed
                                 A QGIS plugin
 This plugin can help you distribute organisation wide news
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2022-04-26
        git sha              : $Format:%H$
        copyright            : (C) 2022 by GeoWerkstatt
        email                : support@geowerkstatt.ch
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os.path
import json
import requests
from .network import networkaccessmanager

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QTimer
from qgis.PyQt.QtGui import QIcon, QPixmap, QImage
from qgis.PyQt.QtWidgets import QAction
from qgis.core import Qgis, QgsMessageLog, QgsSettings
from qgis.PyQt.QtWidgets import QAction, QApplication, QWidget, \
                            QVBoxLayout, QHBoxLayout,\
                            QLabel, QFileDialog

from .custom_news_feed_dockwidget import CustomNewsFeedDockWidget
from .news_feed_settings_dialog import NewsFeedSettingsDialog

class CustomNewsFeed:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.settings = QgsSettings()
        self.nam = networkaccessmanager.NetworkAccessManager()

        # Run plugin when project is opened or created
        self.iface.projectRead.connect(self.run)
        self.iface.newProjectCreated.connect(self.run)

        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'CustomNewsFeed_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.settings_dlg = NewsFeedSettingsDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Custom News Feed')
        self.toolbar = self.iface.addToolBar(u'CustomNewsFeed')
        self.toolbar.setObjectName(u'CustomNewsFeed')

        #print "** INITIALIZING CustomNewsFeed"
        self.dockwidget = None

        # Signals and slots
        self.settings_dlg.browse_btn.clicked.connect(self.choose_file)

        # Add update interval to update news once a day
        self.timer = QTimer()
        self.timer.timeout.connect(self.get_news)
        self.timer.start(86400000)


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.
            Translation is currently not implemented.
        """
        return QCoreApplication.translate('CustomNewsFeed', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.run()
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Neuigkeiten'),
            callback=self.run,
            parent=self.iface.mainWindow())

        icon_path = os.path.join(self.plugin_dir, 'settings.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Settings'),
            callback=self.run_settings,
            add_to_toolbar=False,
            status_tip=self.tr(u'Custom News Feed Settings'),
            parent=self.iface.mainWindow())

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        self.timer.stop()

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Custom News Feed'),
                action)
            self.iface.removeToolBarIcon(action)
        # Remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""
        if self.dockwidget == None:
            self.dockwidget = CustomNewsFeedDockWidget()
        self.dockwidget.closingPlugin.connect(self.onClosePlugin)

        # Show the dockwidget
        self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dockwidget, raiseTab=True)
        self.dockwidget.show()
        self.get_news()


    def get_news(self):
        """Get news content from json-file and display it."""
        news_json_file_path = self.settings.value("CustomNewsFeed/json_file_path", None)
        if not news_json_file_path:
                news_json_file_path = os.path.join(self.plugin_dir, 'sample_news','sample_news.json')
        self.display_news_content(news_json_file_path)


    def display_news_content(self, news_json_file_path):
        """Display content of json-file in plugin."""
        try:
            json_tree = self.get_text_contents_from_path(news_json_file_path)
            news = json.loads(json_tree)
            self.dockwidget.setWindowTitle(news['PanelTitle'])
            self.dockwidget.linkSectionLabel.setText(news['LinkSectionTitle'])
            self.settings_dlg.pathToConfigurationFileLabel.setText(news["PathToConfigurationFileLabel"])
            self.configure_pinned_message(news["PinnedMessage"])
            self.addNews(news["NewsArticles"])
            self.addLinks(news["Links"])

        except Exception as e:
            print(str(e))
            self.iface.messageBar().pushMessage("Error",
                    self.tr(u'Json file konnte nicht geladen werden. ') +
                    self.tr(u'Mehr Informationen im QGis message log.'),
                    level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error Initializing Config file ' + str(e),
                                          'Custom News Plugin')


    def configure_pinned_message(self, pinnedMessageJson):
        """Adds pinned message to plugin in three possible styles."""
        self.dockwidget.pinned_message.setVisible(False)
        self.dockwidget.pinned_message.setText(pinnedMessageJson["Text"])
        if pinnedMessageJson["Text"] is not "":
            self.dockwidget.pinned_message.setVisible(True)
        if pinnedMessageJson["Importance"]=="low" :
            self.dockwidget.pinned_message.setStyleSheet("background:rgb(154, 229, 114);padding:8px;")
        else:
            if pinnedMessageJson["Importance"]=="medium":
                self.dockwidget.pinned_message.setStyleSheet("background:rgb(255, 206, 58);padding:8px;")
            else:
                if pinnedMessageJson["Importance"]=="high":
                    self.dockwidget.pinned_message.setStyleSheet("background:rgb(255, 85, 0);padding:8px;")
                else:
                    self.dockwidget.pinned_message.setStyleSheet("background:rgb(173,216,230);padding:8px;")


    def addLinks(self, links):
        """ Add links to the link section of the plugin."""
        # Only display section if links are available
        self.dockwidget.linksScrollArea.setVisible(len(links) > 0)
        self.dockwidget.linkSectionLabel.setVisible(len(links) > 0)
        self.dockwidget.widget = QWidget()
        self.dockwidget.vbox = QVBoxLayout()
        for link in links:
            label= QLabel("<a href=% s>% s</a>" % (link['Url'], link['LinkTitle']))
            label.setTextFormat(Qt.RichText)
            label.setOpenExternalLinks(True)
            self.dockwidget.vbox.addWidget(label)

        self.dockwidget.widget.setLayout(self.dockwidget.vbox)
        self.dockwidget.linksScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.dockwidget.linksScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dockwidget.linksScrollArea.setWidgetResizable(True)
        self.dockwidget.linksScrollArea.setWidget(self.dockwidget.widget)


    def addNews(self, newsArticles):
        """ Add new articles to the news section of the plugin."""
        self.dockwidget.widget = QWidget()
        self.dockwidget.vbox = QVBoxLayout()

        for index, newsArticle in enumerate(newsArticles):
            hbox = QHBoxLayout()
            left_inner_vbox = QVBoxLayout()
            right_inner_vbox = QVBoxLayout()
            hbox.addLayout(left_inner_vbox)
            hbox.addLayout(right_inner_vbox)

            self.dockwidget.vbox.addLayout(hbox)
            self.dockwidget.vbox.setContentsMargins(15,15,15,15)
            self.dockwidget.vbox.setSpacing(20)

            text= QLabel(newsArticle['Text'])
            text.setWordWrap(True)

            if not newsArticle["ImageUrl"] == "":
                image = QImage()
                image.loadFromData(requests.get(newsArticle["ImageUrl"]).content)
                image_label = QLabel()
                image_label.setFixedSize(150, 150)
                image_label.setPixmap(QPixmap(image).scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                right_inner_vbox.setContentsMargins(0,15,0,0)
                right_inner_vbox.addWidget(image_label)
                right_inner_vbox.addStretch(1)

            title = QLabel(newsArticle['Title'])
            title.setStyleSheet("font-weight: bold")

            date = QLabel(newsArticle['Date'])
            date.setStyleSheet("color: grey")

            link = QLabel("<a href=% s>% s</a>" % (newsArticle['LinkUrl'], newsArticle['LinkTitle']))
            link.setTextFormat(Qt.RichText)
            link.setOpenExternalLinks(True)

            left_inner_vbox.addWidget(title)
            left_inner_vbox.addWidget(date)
            left_inner_vbox.addWidget(text)
            left_inner_vbox.addWidget(link)
            left_inner_vbox.setSpacing(2)
            if index == (len(newsArticles)-1):
                left_inner_vbox.addStretch(1)

        self.dockwidget.widget.setLayout(self.dockwidget.vbox)
        self.dockwidget.newsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.dockwidget.newsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.dockwidget.newsScrollArea.setWidgetResizable(True)
        self.dockwidget.newsScrollArea.setWidget(self.dockwidget.widget)


    def run_settings(self):
        """ Shows the settings dialog"""
        self.settings_dlg.config_json_path.setText(self.settings.value("CustomNewsFeed/json_file_path", ""))
        if self.settings_dlg.config_json_path.text() == "":
            self.settings_dlg.config_json_path.setPlaceholderText("https://")
        self.settings_dlg.show()
        result = self.settings_dlg.exec_()
        if result:
            path = unicode(self.settings_dlg.config_json_path.text())
            self.settings.setValue("CustomNewsFeed/json_file_path", path)
            self.display_news_content(path)


    def choose_file(self):
        """Allows the user to choose a local path for the config file."""
        path = QFileDialog.getOpenFileName(
                    caption = self.tr(u"Wählen Sie eine Konfigurationsdatei aus:"),
                    directory = self.plugin_dir,
                    filter = '*.json')[0]
        self.settings_dlg.config_json_path.setText(path)


    def get_text_content_from_path(self, path):
        """Gets the text content from a path. May be a local path, or an url"""
        txt = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if path[0:4].lower() == 'http':
                (response, content) = self.nam.request(path)
                txt = content.decode("utf-8")
            else:
                if (not os.path.exists(path)) \
                and os.path.exists(os.path.join(self.plugin_dir, path)):
                    path = os.path.join(self.plugin_dir, path)
                with open(path,'r',encoding='utf-8') as f:
                    txt = f.read()
        except Exception as e:            
            self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                self.tr(u'Die Datei ') + path +
                self.tr(u' konnte nicht gelesen werden. ') +
                self.tr(u'Mehr Informationen im QGis message log. Beispielhafe News werden angezeigt.'),
                level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error reading file ' + str(e),'Custom News Feed')
            with open(os.path.join(self.plugin_dir, 'sample_news','sample_news.json'),'r', encoding='utf-8') as f:
                txt = f.read()
        finally:
                QApplication.restoreOverrideCursor()
        return txt