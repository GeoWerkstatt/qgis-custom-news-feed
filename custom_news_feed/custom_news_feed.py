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
import os
import shutil
import os.path
import json
import hashlib

from qgis.PyQt.QtCore import QLocale, QTranslator, QCoreApplication, Qt, QTimer, QUrl, QDir
from qgis.PyQt.QtGui import QIcon, QPixmap, QImage
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest 
from qgis.core import Qgis, QgsMessageLog, QgsBlockingNetworkRequest, QgsApplication, QgsSettings
from qgis.PyQt.QtWidgets import QAction, QApplication, QWidget, \
                            QVBoxLayout, QHBoxLayout,\
                            QLabel, QFileDialog, QPushButton, QSpacerItem

from .custom_news_feed_dockwidget import CustomNewsFeedDockWidget
from .news_feed_settings_dialog import NewsFeedSettingsDialog
from datetime import datetime
from functools import partial
from os.path import abspath, isdir, isfile, join

class CustomNewsFeed:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        
        if os.environ.get("QGIS_DEBUGPY_HAS_LOADED") is None:
            try:
                import debugpy
                debugpy.configure(python=shutil.which("python"))
                debugpy.listen(('localhost', 5678))
            except Exception as e:
                print("Unable to create debugpy debugger: {}".format(e))
            else:
                os.environ["QGIS_DEBUGPY_HAS_LOADED"] = '1'

        # Save reference to the QGIS interface
        self.iface = iface
        self.settings = QgsSettings()

        # Run plugin when project is opened or created
        self.iface.projectRead.connect(self.run)
        self.iface.newProjectCreated.connect(self.run)

        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Initialize locale
        locale = self.settings.value('locale/userLocale', QLocale().name())[0:2]
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
        self.settingspath = abspath(join(QgsApplication.qgisSettingsDirPath(), 'customnewsfeed'))
        self.previous_news_path = os.path.join(self.settingspath,'previous_news.json')
        self.news = None
        self.previousNews = None
        self.hasNewArticles = False
        self.current_pinned_message = ''

        #print "** INITIALIZING CustomNewsFeed"
        self.dockwidget = None

        # Signals and slots
        self.settings_dlg.browse_btn.clicked.connect(self.choose_file)

        # Add update interval to update news once a day
        self.timer = QTimer()
        self.timer.timeout.connect(self.reloadNews)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def prerun(self):
        self.forceShowGui = True
        self.run()

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        self.forceShowGui = False
        self.run()
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Neuigkeiten'),
            callback=self.prerun,
            parent=self.iface.mainWindow())

        icon_path = os.path.join(self.plugin_dir, 'settings.png')
        self.add_action(
            icon_path,
            text=self.tr(u'Settings'),
            callback=self.run_settings,
            add_to_toolbar=False,
            status_tip=self.tr(u'Custom News Feed Settings'),
            parent=self.iface.mainWindow())

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

    def run(self):
        """Run method that loads and starts the plugin"""
        if self.dockwidget == None:
            self.dockwidget = CustomNewsFeedDockWidget()
        self.dockwidget.closingPlugin.connect(self.onClosePlugin)

        # Show the dockwidget
        if not self.dockwidget.isUserVisible():
            self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dockwidget, raiseTab=True)
            self.dockwidget.show()
            self.dockwidget.close()

        self.get_news()

    def get_news(self):
        """Get news content from JSON-file and display it."""
        if self.settings.contains('/pythonplugins/customnewsfeedpath'):
            news_json_file_path = self.settings.value('/pythonplugins/customnewsfeedpath')
        else:
            news_json_file_path = self.settings.value("CustomNewsFeed/json_file_path", None)
        if not news_json_file_path:
            news_json_file_path = os.path.join(self.plugin_dir, 'sample_news','sample_news.json')
        self.display_news_content(news_json_file_path)

    def display_news_content(self, news_json_file_path):
        """Display content of JSON-file in plugin."""
        try:
            self.news = self.load_json_from_file(news_json_file_path)
            self.timer.start(self.news['NewsRefreshInterval'] * 60000 ) # convert minutes in miliseconds
            self.dockwidget.setWindowTitle(self.news['PanelTitle'])
            self.dockwidget.tabWidget.setTabText(0, self.news['PanelTitleFeed'])
            self.dockwidget.tabWidget.setTabText(1, self.news['PanelTitleFeedRepository'])
            self.dockwidget.linkSectionLabel.setText(self.news['LinkSectionTitle'])
            self.settings_dlg.pathToConfigurationFileLabel.setText(self.news["PathToConfigurationFileLabel"])
            self.settings_dlg.openPanelOnNewsCheckBox.setText(self.news["OpenPanelOnNewsCheckBoxLabel"])

            if os.path.exists(self.previous_news_path):
                self.previousNews = self.load_json_from_file(self.previous_news_path)
                self.hasNewArticles = False
            else:
                self.hasNewArticles = True
            
            self.add_pinned_message()
            self.addNews()
            self.addLinks()
            self.store_current_news(news_json_file_path)
            self.show_panel()

        except Exception as e:
            self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin", str(e), level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error Reading Config file, missing field ' + str(e),'Custom News Feed')

    def toggle_message_hashfile(self, event):
        """Toggles pinned messages resized/full-sized state"""
        hash = self.createHash(self.current_pinned_message["Text"])
        if self.check_hashfile(hash) == True:
            self.delete_hashfile(hash)
        else:                      
            self.create_hashfile(hash)
        self.reloadNews

    def add_pinned_message(self):
        """Adds pinned message to plugin in three possible styles."""
        self.dockwidget.pinned_message.setVisible(False)
        self.current_pinned_message = self.get_json_field("PinnedMessage",self.news)
        if self.current_pinned_message is not None:
            previousMessage = self.get_json_field("PinnedMessage",self.previousNews)
            if previousMessage is None or self.current_pinned_message != previousMessage:
                self.hasNewArticles = True

            startdate, enddate = self.getStartEndDate(self.current_pinned_message)
            if self.checkPublishingDate(startdate, enddate) == True:
                self.dockwidget.pinned_message.mousePressEvent = self.toggle_message_hashfile
                self.dockwidget.pinned_message.setText(str(self.current_pinned_message["Text"]))
                if self.check_hashfile(self.createHash(self.current_pinned_message["Text"])) == True :
                    self.dockwidget.pinned_message.setText(self.dockwidget.pinned_message.text()[:60]+ '...')
                else:
                    self.dockwidget.pinned_message.setText(str(self.current_pinned_message["Text"]))

                if self.current_pinned_message["Text"] != "":
                    self.dockwidget.pinned_message.setVisible(True)
                if self.current_pinned_message["Importance"]=="low" :
                    self.dockwidget.pinned_message.setStyleSheet("background:rgb(154, 229, 114);padding:8px;")
                else:
                    if self.current_pinned_message["Importance"]=="medium":
                        self.dockwidget.pinned_message.setStyleSheet("background:rgb(255, 206, 58);padding:8px;")
                    else:
                        if self.current_pinned_message["Importance"]=="high":
                            self.dockwidget.pinned_message.setStyleSheet("background:rgb(255, 85, 0);padding:8px;")
                        else:
                            self.dockwidget.pinned_message.setStyleSheet("background:rgb(173,216,230);padding:8px;")

    def addLinks(self):
        """ Add links to the link section of the plugin."""
        links = self.get_json_field("Links",self.news)
        hasLinks = links is not None and len(links) > 0
        self.dockwidget.linksScrollArea.setVisible(hasLinks)
        self.dockwidget.linkSectionLabel.setVisible(hasLinks)

        if hasLinks:
            widget = QWidget()
            vbox = QVBoxLayout()
            widget.setLayout(vbox)
            self.dockwidget.linksScrollArea.setWidget(widget)

            for link in links:
                label= QLabel("<a href=% s>% s</a>" % (link['Url'], link['LinkTitle']))
                label.setTextFormat(Qt.RichText)
                label.setOpenExternalLinks(True)
                vbox.addWidget(label)
                
            vbox.addStretch(1)

    def checkPublishingDate(self, startdate, enddate):
        """ Checks the date relevance of a news entry by its date range """
        ret = True
        now = datetime.now().isoformat()

        if startdate and enddate:
            return startdate <= now <= enddate
        elif startdate:
            return startdate <= now
        elif enddate:
            return now <= enddate

        return True

    def check_hashfile(self, newsidenty) -> bool:
        """ Checks the existence of a hash file related to the news entry """
        filename = abspath(join(self.settingspath, newsidenty))              
        if os.path.exists(filename):
            return True
        else:
            return False

    def delete_hashfile(self, newsidenty):
        """ Deletes a hash file related to the news entry """
        filename = abspath(join(self.settingspath, newsidenty))
        os.remove(filename)
        self.get_news()

    def create_hashfile(self, newsident, noReload=False):
        """ Creates a hash file related to the news entry """
        filename = abspath(join(self.settingspath, newsident))

        if not QDir(self.settingspath).exists(): QDir().mkdir(self.settingspath)
        if not QDir(filename): 
            file = open(filename, 'w')
            file.close()
        if noReload is not True:
            self.get_news()

    def mark_all_as_read(self, newsArticles):
        """Mark all news as read"""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        for index, newsArticle in enumerate(newsArticles):
            startdate, enddate = self.getStartEndDate(newsArticle)
            if self.check_hashfile(newsArticle["Hash"]) == False and self.checkPublishingDate(startdate, enddate) == True:
                self.create_hashfile(newsArticle["Hash"], True)
        self.get_news()
        QApplication.restoreOverrideCursor()
		
    def getStartEndDate(self, jsonObject):
        """Check the existence of a publishing date range"""
        startdate = self.get_json_field("StartPublishingDate",jsonObject)
        enddate = self.get_json_field("EndPublishingDate",jsonObject)
        return startdate, enddate
    
    def get_json_field(self, fieldName, jsonObject):
        """Check the existence of a json field"""
        if jsonObject is None or fieldName not in json.loads(json.dumps(jsonObject)):
            return None
        else:
            return jsonObject[fieldName]

    def reloadNews(self):
        self.forceShowGui = False
        self.get_news()

    def addNews(self):
        """ Add new articles to the news and news repository section of the plugin."""
        unreadNewsBox = self.create_tab_widget(self.dockwidget.unreadNewsScrollArea)
        newsRepositoryBox = self.create_tab_widget(self.dockwidget.newsRepositoryScrollArea)

        newsArticles = self.get_json_field("NewsArticles",self.news)
        previousNewsArcticles = self.get_json_field("NewsArticles",self.previousNews)
        hasUnreadNews = False

        for newsArticle in newsArticles:
            if self.hasNewArticles is False and previousNewsArcticles is not None and newsArticle not in previousNewsArcticles:
                self.hasNewArticles = True

            articleBox, isUnread = self.create_article_widget(newsArticle)
            if isUnread:
                hasUnreadNews = True
                unreadNewsBox.addWidget(articleBox)

            else:
                newsRepositoryBox.addWidget(articleBox)
        
        unreadNewsBox.addStretch(1)
        newsRepositoryBox.addStretch(1)
        
        self.dockwidget.readAllButton.setText(self.news["ReadAllButtonLabel"])
        self.dockwidget.readAllButton.clicked.connect(partial(self.mark_all_as_read, newsArticles))
        self.dockwidget.readAllButton.setDisabled(hasUnreadNews == False)

        self.dockwidget.tabWidget.setCurrentIndex(0)
        self.dockwidget.setFocus()

        if hasUnreadNews == False:
            self.dockwidget.close()
            if self.check_hashfile(self.createHash(self.current_pinned_message["Text"])):
                self.iface.messageBar().pushMessage("Warning", "Aktuell existieren keine ungelesenen Nachrichten", level=Qgis.Info)

    def show_panel(self):
        if self.hasNewArticles:
            self.iface.messageBar().pushMessage("Info", "Es liegen neue Nachrichten vor!", level=Qgis.Info)
            if self.forceShowGui is False:
                self.forceShowGui = self.settings_dlg.openPanelOnNewsCheckBox.checkState() == Qt.Checked

        if self.forceShowGui and not self.dockwidget.isUserVisible():
            self.dockwidget.show()

        self.forceShowGui = False

    def createHash(self, text):
        return hashlib.md5(str(text).encode('utf-8')).hexdigest()

    def run_settings(self):
        """ Shows the settings dialog"""
        self.settings_dlg.config_json_path.setText(self.settings.value("CustomNewsFeed/json_file_path", ""))
        self.settings_dlg.openPanelOnNewsCheckBox.setCheckState(int(self.settings.value("CustomNewsFeed/open_on_news", Qt.Checked)))
        if self.settings_dlg.config_json_path.text() == "":
            self.settings_dlg.config_json_path.setPlaceholderText("https://")
        self.settings_dlg.show()
        result = self.settings_dlg.exec_()
        if result:
            path = unicode(self.settings_dlg.config_json_path.text())
            self.settings.setValue("CustomNewsFeed/json_file_path", path)
            self.settings.setValue("CustomNewsFeed/open_on_news", self.settings_dlg.openPanelOnNewsCheckBox.checkState())
            self.display_news_content(path)

    def choose_file(self):
        """Allows the user to choose a local path for the config file."""
        path = QFileDialog.getOpenFileName(
                    caption = self.tr(u"Wählen Sie eine Konfigurationsdatei aus:"),
                    directory = self.plugin_dir,
                    filter = '*.json')[0]
        self.settings_dlg.config_json_path.setText(path)

    def load_json_from_file(self, path):
        """Gets the text content from a path. May be a local path, or an url"""
        txt = None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if path[0:4].lower() == 'http':
                request = QNetworkRequest(QUrl(path))
                blockingRequest = QgsBlockingNetworkRequest()
                result = blockingRequest.get(request)
                if result == QgsBlockingNetworkRequest.NoError:
                    reply = blockingRequest.reply()
                    if reply.error() == QNetworkReply.NoError:
                        txt = str(reply.content(), 'utf-8')
                    else:
                        QgsMessageLog.logMessage(u'Error reading file ' + reply.errorString(),'Custom News Feed')
                else:
                    QgsMessageLog.logMessage(u'Error reading file ' + blockingRequest.errorMessage(),'Custom News Feed')
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
                self.tr(u'Mehr Informationen im QGis message log. Beispielhafte News werden angezeigt.'),
                level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error reading file ' + str(e),'Custom News Feed')
            with open(os.path.join(self.plugin_dir, 'sample_news','sample_news.json'),'r', encoding='utf-8') as f:
                txt = f.read()
        finally:
                QApplication.restoreOverrideCursor()

        try:
            json_content = json.loads(txt)
        except Exception as e:
            print(str(e))
            self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                    self.tr(u'JSON-file konnte nicht geladen werden. ') +
                    self.tr(u'Mehr Informationen im QGis message log.'),
                    level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error Initializing Config file ' + str(e),'Custom News Feed')
        return json_content

    def store_current_news(self, news_json_file_path):
        """Stores the current json file in the settings"""
        if not QDir(self.settingspath).exists(): 
            QDir().mkdir(self.settingspath)
        shutil.copyfile(news_json_file_path, self.previous_news_path)

    def create_tab_widget(self, tab):
        """ Creates a layout for the news articles and adds it to the tab """
        widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setContentsMargins(15,15,15,15)
        widget.setLayout(vbox)
        tab.setWidget(widget)
        return vbox

    def create_article_widget(self, newsArticle):
        """ Creates a widget for a news article """
        articleWidget = QWidget()
        articleBox = QHBoxLayout()
        articleBox.setContentsMargins(0,0,0,0)
        articleBox.setSpacing(0)
        articleWidget.setLayout(articleBox)

        textBox = QVBoxLayout()
        articleBox.addLayout(textBox)
        
        title = QLabel(newsArticle['Title'])
        title.setStyleSheet("font-weight: bold")
        textBox.addWidget(title)

        date = QLabel(newsArticle['Date'])
        date.setStyleSheet("color: grey")
        textBox.addWidget(date)

        text= QLabel(newsArticle['Text'])
        text.setWordWrap(True)
        textBox.addWidget(text)
        
        if not newsArticle['LinkTitle'] == "":
            link = QLabel("<a href=% s>% s</a>" % (newsArticle['LinkUrl'], newsArticle['LinkTitle']))
            link.setTextFormat(Qt.RichText)
            link.setOpenExternalLinks(True)
            textBox.addWidget(link)

        newsArticle['Hash'] = self.createHash(str(newsArticle['Title']+newsArticle['Date']))
        startdate, enddate = self.getStartEndDate(newsArticle)
        isUnread = self.check_hashfile(newsArticle['Hash']) == False and self.checkPublishingDate(startdate, enddate) == True
        if isUnread:
            spacer = QSpacerItem(0, 5)
            textBox.addItem(spacer)
            readbutton = QPushButton(self.news['ReadButtonLabel'])
            readbutton.clicked.connect(partial(self.create_hashfile, newsArticle['Hash']))
            readbutton.adjustSize()
            textBox.addWidget(readbutton)

        if not newsArticle["ImageUrl"] == "":
            imageBox = QVBoxLayout()
            image = QImage()
            imageUrl = newsArticle["ImageUrl"]
            try:
                if imageUrl[0:4].lower() == 'http':
                    request = QNetworkRequest(QUrl(imageUrl))
                    blockingRequest = QgsBlockingNetworkRequest()
                    result = blockingRequest.get(request)
                    if result == QgsBlockingNetworkRequest.NoError:
                        reply = blockingRequest.reply()
                        if reply.error() == QNetworkReply.NoError:
                            image.loadFromData(reply.content())
                        else:
                            image = None
                            QgsMessageLog.logMessage(u'Error reading image ' + reply.errorString(),'Custom News Feed')
                    else:
                        image = None
                        QgsMessageLog.logMessage(u'Error reading image ' + blockingRequest.errorMessage(),'Custom News Feed')
                else :
                    with open(imageUrl, 'rb') as file:
                        image.loadFromData(file.read())
            except Exception as e:                                    
                self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                    self.tr(u'Das Bild mit der Url ') + imageUrl +
                    self.tr(u' konnte nicht geladen werden. '),
                    level = Qgis.Critical)
                QgsMessageLog.logMessage(u'Error reading image ' + str(e),'Custom News Feed')
            if image is not None:
                image_label = QLabel()
                image_label.setFixedWidth(150)
                image_label.setPixmap(QPixmap(image).scaledToWidth(150, Qt.SmoothTransformation))
                imageBox.setContentsMargins(10,15,0,0)
                imageBox.addWidget(image_label)
                articleBox.addLayout(imageBox)
        
        articleBox.setContentsMargins(0,0,0,10)
        return articleWidget, isUnread