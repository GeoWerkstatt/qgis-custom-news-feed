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
import hashlib

from qgis.PyQt.QtCore import QLocale, QTranslator, QCoreApplication, Qt, QTimer, QUrl, QDir
from qgis.PyQt.QtGui import QIcon, QPixmap, QImage
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest 
from qgis.core import Qgis, QgsMessageLog, QgsBlockingNetworkRequest, QgsApplication, QgsSettings
from qgis.PyQt.QtWidgets import QAction, QApplication, QWidget, \
                            QVBoxLayout, QHBoxLayout,\
                            QLabel, QFileDialog, QPushButton

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

        #print "** INITIALIZING CustomNewsFeed"
        self.dockwidget = None

        # Signals and slots
        self.settings_dlg.browse_btn.clicked.connect(self.choose_file)
        self.current_pinned_message = ''

        # Add update interval to update news once a day
        self.timer = QTimer()
        self.timer.timeout.connect(self.get_news)

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
        if not self.dockwidget.isUserVisible():
            self.iface.addTabifiedDockWidget(Qt.RightDockWidgetArea, self.dockwidget, raiseTab=True)
            self.dockwidget.show()
            #self.dockwidget.close()
        self.get_news()


    def get_news(self):
        """Get news content from JSON-file and display it."""
        if self.settings.contains('/pythonplugins/customnewsfeedpath'):
            news_json_file_path = self.settings.value('/pythonplugins/customnewsfeedpath')
        else:
            news_json_file_path = self.settings.value("CustomNewsFeed/json_file_path", None)
        if not news_json_file_path:
            news_json_file_path = os.path.join(self.plugin_dir, 'sample_news','sample_news.json')
        QgsMessageLog.logMessage(u'Reading feed from: ' + news_json_file_path,'Custom News Feed')
        self.display_news_content(news_json_file_path)


    def display_news_content(self, news_json_file_path):
        """Display content of JSON-file in plugin."""
        json_tree = self.get_text_content_from_path(news_json_file_path)
        try:
            news = json.loads(json_tree)
        except Exception as e:
            print(str(e))
            self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                    self.tr(u'JSON-file konnte nicht geladen werden. ') +
                    self.tr(u'Mehr Informationen im QGis message log.'),
                    level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error Initializing Config file ' + str(e),'Custom News Feed')
        try:
            self.timer.start(news['NewsRefreshInterval'] * 60000 ) # convert minutes in miliseconds
            self.dockwidget.setWindowTitle(news['PanelTitle'])
            self.dockwidget.tabWidget.setTabText(0, news['PanelTitleFeed'])
            self.dockwidget.tabWidget.setTabText(1, news['PanelTitleFeedRepository'])
            self.dockwidget.linkSectionLabel.setText(news['LinkSectionTitle'])
            self.settings_dlg.pathToConfigurationFileLabel.setText(news["PathToConfigurationFileLabel"])
            if self.checkPublishingDate(news["PinnedMessage"]['StartPublishingDate'],news["PinnedMessage"]['EndPublishingDate']) == True:
                self.current_pinned_message = news["PinnedMessage"]
                self.configure_pinned_message(news["PinnedMessage"])
            else:
                self.dockwidget.pinned_message.setVisible(False)
            self.addNews(news["NewsArticles"])
            self.addLinks(news["Links"])
        except Exception as e:
            self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                    self.tr(u'Das Feld ' + str(e) + ' ist im angegebenen JSON-file nicht vorhanden.'),
                    level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error Reading Config file, missing field ' + str(e),'Custom News Feed')


    def toggle_message_hashfile(self, event):
        """Toggles pinned messages resized/full-sized state"""
        hash = hashlib.md5(str(self.current_pinned_message["Text"]).encode('utf-8')).hexdigest()
        if self.check_hashfile(hash) == True :
            self.delete_hashfile(hash)
        else:                      
            self.create_hashfile(hash)


    def configure_pinned_message(self, pinnedMessageJson):
        """Adds pinned message to plugin in three possible styles."""
        self.dockwidget.pinned_message.setVisible(False)
        self.dockwidget.pinned_message.mousePressEvent = self.toggle_message_hashfile
        self.dockwidget.pinned_message.setText(str(self.current_pinned_message["Text"]))
        if self.check_hashfile(hashlib.md5(str(pinnedMessageJson["Text"]).encode('utf-8')).hexdigest()) == True :
            self.dockwidget.pinned_message.setText(self.dockwidget.pinned_message.text()[:60]+ '...')
        else:
            self.dockwidget.pinned_message.setText(str(self.current_pinned_message["Text"]))

        if pinnedMessageJson["Text"] != "":
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
        self.dockwidget.widget2 = QWidget()
        self.dockwidget.vbox = QVBoxLayout()
        self.dockwidget.vbox2 = QVBoxLayout()
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


    def checkPublishingDate(self, startdate, enddate):
        """ Checks the date relevance of a news entry by its date range """
        ret = True
        now = datetime.now().isoformat()

        if (startdate is not None) and (enddate is not None):
            if startdate <= now and enddate >= now: ret = True
            else: ret = False
        if (startdate is not None) and (enddate is None):        
            if startdate > now: ret = False
        if (enddate is not None) and (startdate is None): 
            if enddate < now: ret = False

        return ret

    def check_hashfile(self, newsident) -> bool:
        """ Checks the existence of a hash file related to the news entry """
        path = abspath(join(QgsApplication.qgisSettingsDirPath(), 'customnewsfeed'))
        filename = abspath(join(path, newsident))
                
        if os.path.exists(filename):
            return True
        else:
            return False

    def delete_hashfile(self, newsident):
        """ Deletes a hash file related to the news entry """
        path = abspath(join(QgsApplication.qgisSettingsDirPath(), 'customnewsfeed'))
        filename = abspath(join(path, newsident))
        os.remove(filename)
        self.get_news()

    def create_hashfile(self, newsident):
        """ Creates a hash file related to the news entry """
        path = abspath(join(QgsApplication.qgisSettingsDirPath(), 'customnewsfeed'))
        filename = abspath(join(path, newsident))

        if not QDir(path).exists(): QDir().mkdir(path)
        if not QDir(filename): 
            file = open(filename, 'w')
            file.close()
        self.get_news()

    def addNews(self, newsArticles):
        """ Add new articles to the news section of the plugin."""
        self.dockwidget.widget = QWidget()
        self.dockwidget.widget2 = QWidget()
        self.dockwidget.vbox = QVBoxLayout()
        self.dockwidget.vbox2 = QVBoxLayout()

        widgetcount=0

        for index, newsArticle in enumerate(newsArticles):

            # check the existence of a publishing date range
            startdate = enddate = None
            if 'StartPublishingDate' in json.loads(json.dumps(newsArticle)): startdate = newsArticle['StartPublishingDate'] 
            if 'EndPublishingDate' in json.loads(json.dumps(newsArticle)): enddate = newsArticle['EndPublishingDate'] 
            #if self.checkPublishingDate(startdate, enddate) == False: continue

            # create hash as identifier
            newsArticle['Hash'] = hashlib.md5(str(newsArticle['Title']+newsArticle['Date']).encode('utf-8')).hexdigest()

            hbox = QHBoxLayout()
            left_inner_vbox = QVBoxLayout()
            right_inner_vbox = QVBoxLayout()
            hbox.addLayout(left_inner_vbox)
            hbox.addLayout(right_inner_vbox)

            self.dockwidget.vbox.addLayout(hbox)
            self.dockwidget.vbox.setContentsMargins(15,15,15,15)
            self.dockwidget.vbox.setSpacing(20)

            #check if hashfile exists (which indicates that the article is marked as read)
            if self.check_hashfile(newsArticle['Hash']) == False and self.checkPublishingDate(startdate, enddate) == True:

                text= QLabel(newsArticle['Text'])
                text.setWordWrap(True)

                if not newsArticle["ImageUrl"] == "":
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
                                    image = None;
                                    QgsMessageLog.logMessage(u'Error reading image ' + reply.errorString(),'Custom News Feed')
                            else:
                                image = None;
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
                        right_inner_vbox.setContentsMargins(0,5,0,0)
                        right_inner_vbox.addWidget(image_label)
                        right_inner_vbox.addStretch(1)

                title = QLabel(newsArticle['Title'])
                title.setStyleSheet("font-weight: bold")

                readbutton = QPushButton('als gelesen markieren')
                #readbutton.setStyleSheet("qproperty-icon: url(:/path/to/images.png);");
                readbutton.clicked.connect(partial(self.create_hashfile, newsArticle['Hash']))
                readbutton.adjustSize()

                date = QLabel(newsArticle['Date'])
                date.setStyleSheet("color: grey")

                link = QLabel("<a href=% s>% s</a>" % (newsArticle['LinkUrl'], newsArticle['LinkTitle']))
                link.setTextFormat(Qt.RichText)
                link.setOpenExternalLinks(True)

                left_inner_vbox.addWidget(title)
                left_inner_vbox.addWidget(date)
                left_inner_vbox.addWidget(text)
                left_inner_vbox.addWidget(link)
                left_inner_vbox.addWidget(readbutton)
                left_inner_vbox.setSpacing(2)
                widgetcount = widgetcount+1
                #left_inner_vbox.addStretch(1)

                self.dockwidget.vbox.addStretch(1)

                self.dockwidget.widget.setLayout(self.dockwidget.vbox)
                self.dockwidget.newsScrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.dockwidget.newsScrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.dockwidget.newsScrollArea.setWidgetResizable(True)
                self.dockwidget.newsScrollArea.setWidget(self.dockwidget.widget)

            else:

                hbox2 = QHBoxLayout()
                left_inner_vbox2 = QVBoxLayout()
                right_inner_vbox2 = QVBoxLayout()
                hbox2.addLayout(left_inner_vbox2)
                hbox2.addLayout(right_inner_vbox2)

                self.dockwidget.vbox2.addLayout(hbox2)
                self.dockwidget.vbox2.setContentsMargins(15,15,15,15)
                self.dockwidget.vbox2.setSpacing(20)

                text2= QLabel(newsArticle['Text'])
                text2.setWordWrap(True)

                if not newsArticle["ImageUrl"] == "":
                    image2 = QImage()
                    imageUrl2 = newsArticle["ImageUrl"]
                    try:
                        if imageUrl2[0:4].lower() == 'http':
                            request2 = QNetworkRequest(QUrl(imageUrl2))
                            blockingRequest2 = QgsBlockingNetworkRequest()
                            result2 = blockingRequest2.get(request2)
                            if result2 == QgsBlockingNetworkRequest.NoError:
                                reply2 = blockingRequest2.reply()
                                if reply2.error() == QNetworkReply.NoError:
                                    image2.loadFromData(reply2.content())
                                else:
                                    image2 = None;
                                    QgsMessageLog.logMessage(u'Error reading image ' + reply2.errorString(),'Custom News Feed')
                            else:
                                image2 = None;
                                QgsMessageLog.logMessage(u'Error reading image ' + blockingRequest2.errorMessage(),'Custom News Feed')
                        else :
                            with open(imageUrl2, 'rb') as file2:
                                image2.loadFromData(file2.read())
                    except Exception as e:                                    
                        self.iface.messageBar().pushMessage("Fehler im Custom News Feed Plugin",
                            self.tr(u'Das Bild mit der Url ') + imageUrl2 +
                            self.tr(u' konnte nicht geladen werden. '),
                            level = Qgis.Critical)
                        QgsMessageLog.logMessage(u'Error reading image ' + str(e),'Custom News Feed')
                    if image2 is not None:
                        image_label2 = QLabel()
                        image_label2.setFixedWidth(150)
                        image_label2.setPixmap(QPixmap(image2).scaledToWidth(150, Qt.SmoothTransformation))
                        right_inner_vbox2.setContentsMargins(0,5,0,0)
                        right_inner_vbox2.addWidget(image_label2)
                        right_inner_vbox2.addStretch(1)

                title2 = QLabel(newsArticle['Title'])
                title2.setStyleSheet("font-weight: bold")

                #readbutton2 = QPushButton(newsArticle['Hash'])
                #readbutton2.clicked.connect(partial(self.create_hashfile, readbutton2.text()))
                #readbutton2.adjustSize()

                date2 = QLabel(newsArticle['Date'])
                date2.setStyleSheet("color: grey")

                link2 = QLabel("<a href=% s>% s</a>" % (newsArticle['LinkUrl'], newsArticle['LinkTitle']))
                link2.setTextFormat(Qt.RichText)
                link2.setOpenExternalLinks(True)

                left_inner_vbox2.addWidget(title2)
                left_inner_vbox2.addWidget(date2)
                left_inner_vbox2.addWidget(text2)
                left_inner_vbox2.addWidget(link2)
                #left_inner_vbox2.addWidget(readbutton2)
                left_inner_vbox2.setSpacing(2)
                left_inner_vbox2.addStretch(1)

                self.dockwidget.vbox2.addStretch(1)

                self.dockwidget.widget2.setLayout(self.dockwidget.vbox2)
                self.dockwidget.newsScrollArea2.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
                self.dockwidget.newsScrollArea2.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                self.dockwidget.newsScrollArea2.setWidgetResizable(True)
                self.dockwidget.newsScrollArea2.setWidget(self.dockwidget.widget2)    
          
            self.dockwidget.tabWidget.setCurrentIndex(0)

        #if left_inner_vbox.count() == 0: 
        if widgetcount == 0 and self.check_hashfile(hashlib.md5(str(self.current_pinned_message["Text"]).encode('utf-8')).hexdigest()) == True :
            self.dockwidget.close()
            self.iface.messageBar().pushMessage("Warning", "Aktuell existieren keine ungelesenen Nachrichten", level=Qgis.Warning)
        else:
            if self.dockwidget.isUserVisible():
                self.dockwidget.show()
            else:
                self.iface.messageBar().pushMessage("Warning", "Es liegen neue Nachrichten vor!", level=Qgis.Warning)                


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
                self.tr(u'Mehr Informationen im QGis message log. Beispielhafe News werden angezeigt.'),
                level = Qgis.Critical)
            QgsMessageLog.logMessage(u'Error reading file ' + str(e),'Custom News Feed')
            with open(os.path.join(self.plugin_dir, 'sample_news','sample_news.json'),'r', encoding='utf-8') as f:
                txt = f.read()
        finally:
                QApplication.restoreOverrideCursor()
        return txt