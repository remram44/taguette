---
hide:
  - toc
---

# Using Taguette

## :material-open-in-app: Open Taguette

If you've downloaded and installed Taguette on your computer, you should be able to double-click on the Taguette icon and start it up! You'll see the command line will pop up and be running. This is ok! Don't worry about the terminal but do leave it running. If you exit the terminal, Taguette will stop. Taguette should automatically pop up in your web browser, but if for some reason it doesn't, navigate to [`localhost:7465`](http://localhost:7465/) to begin working on your projects! It should look something like this (if you're using Taguette on a server, you should see 'account' where 'single-user mode' is):

![00_open.png](img%2Fguide%2F00_open.png)

You will see a page that greets you as the admin and has a button to _Create a project_ or _Import a project_.

## :material-database-import-outline: Import an existing project

To import your project onto another instance of Taguette (for instance, a locally running copy on your computer or another server), from the welcome screen click "Import a project file". From there, you select a project (`SQLite3` file extension only) to upload:

![01_import.png](img%2Fguide%2F01_import.png)

Click 'Browse' and select the file. Taguette will confirm on this screen the name of the project, and once you hit "Import", all project materials will be imported!

If you want to browse the database directly, you can find documentation about the schema in [our internal documentation](https://gitlab.com/remram44/taguette/-/blob/master/ARCHITECTURE.md#the-database). You can open in it in something like [DB Browser](https://sqlitebrowser.org/) or any tool that can open `SQLite 3`.

## :material-newspaper-plus: Create a new project

You can also start a fresh project from the first page of Taguette. Click the **Create a project** button and you'll be prompted to enter a 'Title' and 'Description' for your new project. This can be changed later on if you want, but we highly recommend adding this from the start if possible:

![02-create.png](img%2Fguide%2F02-create.png)

Upon clicking 'Create', you'll be taken to the **Project View**, which has a left and a right pane:

![03-panes.png](img%2Fguide%2F03-panes.png)

The left pane contains the information about your project information ('Project Info'), uploaded materials ('Documents'), and tags ('Highlights') as tabs. You can go between these tabs as you like. The right pane will render documents and will be the area where you'll do the highlighting and tagging, as well as exporting.

## :material-file-document-plus: Add documents

To get an idea of how to work in Taguette, let's upload a document and get you tagging! In the left pane, click on the **Documents** tab. You should see a button that says **Add a document**. Click that and pick just one document from your computer, either a: `.pdf`, `.docx`, `.txt`, `.odt`, `.md`, or `.html`.

![04-docs.png](img%2Fguide%2F04-docs.png)

Right now, you can only upload one file at at time. You'll be prompted to give the new document a **Name** (should be something human-readable, required) and **Description** (a note about the file, optional). When you have picked a document and at least given it a name, click the 'Import' button.

![05-upload.png](img%2Fguide%2F05-upload.png)

You should then see that file immediately in the Documents tab. If not, just refresh the page and it should be shown then. If you cannot see your document, you might be uploading a file type that Taguette cannot yet handle. Please let us know at [hi@taguette.org](mailto:hi@taguette.org).

## :material-tag: Tags

Taguette ships with one existing tag (or codes, if you're familiar with qualitative research): `interesting`. This is just there to get you started -- you can add and remove tags as often as you'd like! To view all your existing tags, click the **Highlights** tab in the left pane. You will see a list of tags you have and a count of the number of times you have highlighted your materials with a given tag.

![06-taglist.png](img%2Fguide%2F06-taglist.png)

You should see a list of existing tags for the project - again, if you haven't added any yet, you will still see `interesting`.

### :material-tag-plus: Create Tags

To add your own tags to this project, click **Create a tag**. You will get a popup asking you for the **Name** and **Description** of the tag you want to create:

![07-newTag.png](img%2Fguide%2F07-newTag.png)

After you give the tag a useful name and a bit of description about what it means, you should see it added to the list in alphabetical order.

**A note on hierarchical tagging**: you can use any punctuation to make hierarchies. So `tech.floss` lives underneath `tech`. If I click on `tech.floss`, then I'll see only materials relating to that tag. If I click on `tech`, I'll see everything in that tag as well as `tech.floss` and any other sub-tag.

### :material-tag-edit: Change or delete tags

You can also change or delete a tag by clicking the **edit** badge to the right of the name of the tag in the list. This will bring you to a popup where you can edit the name of the tag, its description, or you can click the grey _Delete_ button next to the blue _Save & Close_ button.

![08-changeTag.png](img%2Fguide%2F08-changeTag.png)

### :material-tag-multiple: Merge Tags

If you want to merge one tag into another, you can also do this from the edit window. Click the **edit** badge to the right of the name of the tag in the list. This will bring you back to the same popup for editing and deleting a tag. Instead, if you click **Merge**, then you will be prompted to select the tag that you want to merge into. Once you select a tag and click **Merge tags**, then all the highlights for the first tag will be moved to the second tag.

![09-mergeTag.png](img%2Fguide%2F09-mergeTag.png)

### :material-application-import: Import a codebook

If you have an existing codebook from another program, you can import it into Taguette in `CSV` format. Existing tags will not be deleted, new tags will be added alongside them.

Go to the **Project Info** tab and click on **Import a codebook**:

![10-projectMenu.png](img%2Fguide%2F10-projectMenu.png)

The file should have a column for the tag names, called 'name' or 'tag' or 'path'. It can also optionally have a column called 'description'. Other columns are ignored. Structure the codebook for importing like so:

| tag        | description                                     |
|------------|-------------------------------------------------|
| family     | mentions of family                              |
| tragedy    | mentions of tragedy the participant experienced |
| obstinence | stubbornness expressed by the participant       |

You will be able to select the project in which to import the codebook. Click "Browse" and you will be able to select the `CSV` file you want to upload:

![11-import-codebook.png](img%2Fguide%2F11-import-codebook.png)

## :material-format-color-highlight: Highlighting

Once uploaded, you should see any and all documents in the **Documents** tab. Clicking on one of those will have the text appear on the right pane, ready for highlighting! 

![12-viewDoc.png](img%2Fguide%2F12-viewDoc.png)

### :material-pen-plus: Add highlight

Once you see the text in the right pane, we can start highlighting it! Select some text by left-clicking and dragging it over the text you'd like to highlight. Once you let go of your left-click, a pop-up that says **new highlight** will appear next to the highlighted text:

![13-highlightText.png](img%2Fguide%2F13-highlightText.png)

Click that pop-up, and you will get a list of existing tags from which to choose. You can select one or more tags to apply to the highlighted text:

![14-addHighlight.png](img%2Fguide%2F14-addHighlight.png)

If you want to create a new tag in the moment instead of using one that already exists, then simply click 'Create a tag', and you'll be sent to the same popup where you made tags earlier. Once you make your tag, you'll be dropped back into the popup above where you should select a tag for the highlighted text. 

![15-createTagHighlight.png](img%2Fguide%2F15-createTagHighlight.png)

After you've **checked off which tags you'd like to associate with the highlighted text**, click 'Save & Close', and the text you've just tagged should now be highlighted with the color associated with the tag (e.g. bright yellow).

### :material-pen-minus: Delete highlight

If you've accidentally tagged a section of text you didn't want to, you can delete it by **clicking on the highlighted text**. This will give you the same pop-up window that you used to tag it. Next to the save button, there is a red button called **Delete highlight**. Click that, and the highlight will be removed from the text. It should no longer be bright yellow nor have any tags associated with it.

### :material-file-document-multiple-outline: View highlighted & tagged text

If you want to see all the highlighted text associated with a specific tag, first go to the **Highlights** tab in the left pane. Click a tag, and in the right pane, you will see a list of quotes with a blue link to the document where they originated from and all their associated tags with a black badge. The tag on the left pane will also be highlighted:

![16-specificHighlight.png](img%2Fguide%2F16-specificHighlight.png)

If you want to see all the highlighted text for **all documents and all tags**, click **See all highlights** and you will see a list of quotes with a blue link to the document where they originated from and all their associated tags with a black badge:

![17-allHighlights.png](img%2Fguide%2F17-allHighlights.png)

You can also view the document with all its highlights by navigating to the **Documents** tab in the left pane. Then just click on the document you wish to view, and if you've highlighted it, you should see:

![18-highlightedDoc.png](img%2Fguide%2F18-highlightedDoc.png)

If you hover your mouse over a highlighted section of text, you will see tags in a tooltip to the right of your mouse cursor. 

### :material-lightbulb-night-outline: Backlight documents

To explore your highlighted document in a different way, you can try clicking on the **Backlight** checkbox. You can see it at the bottom of the pane. It will grey out all the non-highlighted text to make the highlighted text really pop. We found this to be a nice view for exploring the texts differently:

![19-backlight.png](img%2Fguide%2F19-backlight.png)

## :material-application-export: Export options

You can export everything out of Taguette that you put in: tags, highlights, codebooks, documents, and even the entire project!

### :material-home-export-outline: Export codebook

To export the codebook of your project - this is a list of all the tags that you've created alongside their description - use the dropdown menu in the **Project** tab in the left pane of Taguette, underneath the project description. There is a variety of export options, including `QDC` (REFI-QDA standard), `CSV` (spreadsheet), `XLSX` (Microsoft Excel), `DOCX` (Microsoft Word), `HTML`, and `PDF`.

![20-exportCodebook.png](img%2Fguide%2F20-exportCodebook.png)

###  :material-file-document-arrow-right-outline: Export highlights

To export all the associated highlights for a given tag, navigate to the Highlights tab in the left pane, and click on the tag of the highlights you'd want to export. Then you can use the Export this view dropdown menu at the top right in the right pane. You will have a choice of `HTML` (a webpage), `CSV`, `XLSX`, `DOCX` (editable), or `PDF` (not easily editable). While you will see the document with all the highlights, right now you won't be able to tell from that doc which tags go with the highlights.

![21-exportTag.png](img%2Fguide%2F21-exportTag.png)

You will see all the highlighted text for the particular tag with information about each highlight right underneath it -- which document it came from, and which tags are associated with it. This is how it looks with the `DOCX` export:

![22-exportTagEX.png](img%2Fguide%2F22-exportTagEX.png)

To export all the highlights with all associated tags, navigate to the **Highlights** tab in the left pane, and click on **See all highlights**. Then you can use the **Export this view** dropdown menu at the top right in the right pane. Again, you will have a choice of `HTML`, `DOCX`, or `PDF`.

![23-exportAllTags.png](img%2Fguide%2F23-exportAllTags.png)

You will see all the highlighted text for all tags with information about it -- which document it came from, and which tags are associated with it. This is how it looks with the `DOCX` export:

![24-exportAllTagEX.png](img%2Fguide%2F24-exportAllTagEX.png)

### :material-file-export-outline: Export documents

To export the document that you've highlighted, first navigate to the **Documents** tab in the left pane, and click on the document that you want to export. Then you can use the **Export this view** dropdown menu at the top right in the right pane. Again, you will have a choice of `HTML`, `DOCX`, or `PDF`.

![25-exportDoc.png](img%2Fguide%2F25-exportDoc.png)

You will see the document with your highlight in yellow, and the associated tag(s) next to the highlighted text, itself highlighted in light red and in brackets. Yellow is the quote, light red are the tag(s). This is how it looks with the `DOCX` export:

![26-exportDocEXs.png](img%2Fguide%2F26-exportDocEXs.png)

### :material-database-export-outline: Export project file

You can also export projects in Taguette! To export your project, go to the **Project Info** tab in the left pane. You should see a button that says **Export project**. Click that, and you should get a download started of a `SQLite3` file. This holds your Taguette project, all files, as well as all highlights and codes:

![27-exportProject.png](img%2Fguide%2F27-exportProject.png)

It will be named with the date the project was exported and it's name.

## :material-server-network-outline: Server-only settings

### :material-translate: Change interface language

If you are working on [app.taguette.org](https://app.taguette.org/) or hosting Taguette on your own server, you have the option to change the language of the interface. In the upper righthand corner, you should see a dropdown menu labeled "Account". Click that dropdown, and then click "Settings." You will see a dropdown menu in your profile settings to change the language that Taguette will be in. By default, it will auto-detect a language from your Internet browser.

![28-language.png](img%2Fguide%2F28-language.png)

If you do not see your language represented in this list, we would encourage you to add a translation via our Transifex project: [https://www.transifex.com/remram44/taguette](https://www.transifex.com/remram44/taguette/) or by sending us a `.po` file via GitLab, instructions: [https://gitlab.com/remram44/taguette/-/tree/master/po](https://gitlab.com/remram44/taguette/-/tree/master/po).

### :material-human-greeting-proximity: Adding collaborators

If you are working on [app.taguette.org](https://app.taguette.org/) or hosting Taguette on your own server, you have the option to work with others! In the **Project Info** tab of your Taguette project, you should see a grey button labeled **Manage Collaborators**:

![29-projectCollab.png](img%2Fguide%2F29-projectCollab.png)

Click that and you should get a modal with the option to add and remove collaborators, as well as change their permissions on the project. You must add their Taguette username and pick from the list of permissions, click **Add to project**, and to make sure that you've fully added your collaborator, next click 'Save & Close'.

![30-collabs.png](img%2Fguide%2F30-collabs.png)

You can add collaborators with the following permissions:

| Permission Level                              | View project     | Change highlights | Change tags      | Add/delete docs  | Change collaborators | Delete project   |
|-----------------------------------------------|------------------|-------------------|------------------|------------------|----------------------|------------------|
| **Full permission**                           | :material-check: | :material-check:  | :material-check: | :material-check: | :material-check:     | :material-check: |
| **Can't change collaborators/delete project** | :material-check: | :material-check:  | :material-check: | :material-check: |                      |                  |
| **View and make changes**                     | :material-check: | :material-check:  | :material-check: |                  |                      |                  |
| **View only**                                 | :material-check: |                   |                  |                  |                      |                  |
