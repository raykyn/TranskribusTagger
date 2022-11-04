# TranskribusTagger (Version 0.1.1)
This script obtains Transkribus PageXML via API, annotates them with a flairNLP SequenceTagger (e.g. Named Entity Recognition) and then automatically uploads the changed documents via API to Transkribus.

## Usage
```
usage: automated_tagging.py [-h] -u USER -m MODEL [-c COLL] [-d DOC]
                            [-p PAGES] [-s STATUS] [--comment COMMENT]
                            [--debug]

Access Transkribus documents via API, annotate them, then upload the annotated
documents.

optional arguments:
  -h, --help            show this help message and exit
  -u USER, --user USER  Transkribus username. Required.
  -m MODEL, --model MODEL
                        Enter path to model to use. Uses flair syntax, which
                        means you can directly access models hosted on
                        huggingface this way. Required.
  -c COLL, --coll COLL  Collection IDs or regex expression of collection
                        names, multiple collections can be entered by
                        separating by a comma. Omitting this will process all
                        collections accessible to the user.
  -d DOC, --doc DOC     Document IDs or regex expression of document names,
                        multiple documents can be entered by separating by a
                        comma. Omitting this will process all documents
                        accessible to the user in the defined collections.
  -p PAGES, --pages PAGES
                        Enter single integers or a range of pages, e.g.
                        "3-42". You can also enter multiple ranges or numbers
                        by separating them by a comma. Only really useful if
                        you're processing a single document, but whatever
                        floats your boat.
  -s STATUS, --status STATUS
                        Which version of the document should be annotated?
                        Default will use the latest version, but you can
                        instead enter any status you might prefer like "Ground
                        Truth" or "Final". If multiple versions of the given
                        status exist for the document, only the newest version
                        will be processed. Mind you that any documents that do
                        not contain a version with the defined status will not
                        be processed.
  --comment COMMENT     Pass a custom comment which will be visible in
                        Transkribus in the "Message" column. E.g. use to note
                        which NER model was used.
  --debug               Get some additional info for debugging purposes.
  ```
  
  Example which would process all documents in all collections that the user has access to:
  ```python3 automated_tagging.py -u example@example.mail -m de-ner-large --comment "Automated Annotation."```
  
  ## Requirements
  - Python 3.8 or newer (probably also works with older Python 3.X versions, but not tested)
  - flair (https://github.com/flairNLP/flair)
  
  If you do not have a device with a CUDA-compatible video card, the tagging process will be very slow, and I would recommend doing this only for a few pages at once, e.g. for testing. If you want to process a large collection of documents, consider obtaining a device with a CUDA-compatible video card, or using a cloud platform like Google Colab.
  
  ## Notes
  - This script is still very much in development and bugs must be expected. Please report any unwanted bevior to us.
  

## Changelog
- Version 0.1.1 (4.11.2022): Fixed bug which caused annotations to be shifted when a hyphen appeared mid-text.
