# Custom News Feed

## What do I use Custom News Feed for?

Custom News Feed is a [QGIS](https://www.qgis.org/en/site/) plugin that lets you display a feed of articles containing a title, date, text, image and link. The information to display is managed in a JSON-file, that can be provided locally or via url.
Custom News Feed plugin is helpful if you want to distriubte news articles organisation-wide.
News entries can be marked as read, so that they disappear. For news articles this can be done by clicking the related button. Pinned Messages can be shortened/extended by clicking onto the message field itself.
News articles can have a start- and/or an end-publishing date. A pinned message needs to have such entries.

![](dockpane_preview.png)

## Where can I get it?

Install [Custom News Feed](https://plugins.qgis.org/plugins) directly in QGIS by using the [Plugins menu](http://docs.qgis.org/latest/en/docs/user_manual/plugins/plugins.html).

## License

The Custom News Feed plugin is licensed under the [GPL-3.0 license](LICENSE).
Copyright © 2022 [GeoWerkstatt GmbH](https://www.geowerkstatt.ch)

## Configuration file

The JSON-file used to display your custom news has the following properties.

    "PanelTitle" : string (mandatory),
    "PanelTitleFeed" : string (mandatory),
    "PanelTitleFeedRepository" : string (mandatory),
    "ReadButtonLabel" : string (mandatory),
    "ReadAllButtonLabel" : string (mandatory),

#### Articles which will be displayed in the main section of the plugin window

    "NewsArticles": array of objects [
            {
                "Title":string (mandatory),
                "Date": string (mandatody),
                "Text":string (mandatory),
                "LinkUrl":string (optional),
                "LinkTitle": string (optional),
                "ImageUrl": url (optional),
                "StartPublishingDate": iso.datetime (like "2023-05-12T06:00:00.000Z", optional),
                "EndPublishingDate": iso.datetime (like "2023-05-12T06:00:00.000Z", optional)
            },
            {
                ...
            }
        ],

#### Links which will be displayed below the main section of the plugin window

        "LinkSectionTitle" : string (mandatory),
        "Links": [
            {
                "Url":url (optional)
                "LinkTitle": string (optional)
            },
        ],

#### Message which will be displayed at the top of the news articles in green (low importance), yellow (medium importance) or red (high importance)

        "PinnedMessage": {
            "Text": string (optional),
            "Importance": 'high', 'medium' or 'low' (optional),
            "StartPublishingDate": iso.datetime (like "2023-05-12T06:00:00.000Z", optional),
            "EndPublishingDate": iso.datetime (like "2023-05-12T06:00:00.000Z", optional)
        }

#### Label for the input box to select configuration file (locally or via url)

        "PathToConfigurationFileLabel": string (optional),

#### Label for the checkbox to open the plugin window automatically when a new news article is available

        "OpenPanelOnNewsCheckBoxLabel": string (optional),

#### Time interval (in minutes) after which the plugin rereads the configuration file

        "NewsRefreshInterval": 60
    }

#### Configure the path to the News Feed in qgis_global_settings.ini

A valid entry in this file overwrites the configuration coming from the settings dialog:

```
[pythonplugins]
# path to the news feed json-file. This setting wins - in the case it exists -  against the plugin setting.
customnewsfeedpath=//share/folder/sample_news.json
# possible values: 0: don't open panel if there are new news/ 2: open panel if there are new news
open_on_news=0|2
```

## Debugging

1. Open the _OSGeo4W_ shell and run `pip3 install debugpy`
2. In _QGIS > Settings > Options - System_ append the _Environment_ variables with `QGIS_PLUGIN_USE_DEBUGGER=debugpy` and `QGIS_PLUGINPATH={YourLocalPluginDirectory}`
3. Install the QGIS plugin _Plugin Reloader_ to enable reloading the plugin without restarting QGIS
4. Restart QGIS for the changes to take effect and open the plugin
5. Start the debugger in VS Code with the launch configuration _Python: Remote Attach_
