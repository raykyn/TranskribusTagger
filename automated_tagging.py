#! /usr/bin/python3

#from lxml import etree as et
import xml.etree.ElementTree as et
from flair.models import SequenceTagger
from flair.data import Sentence
from collections import defaultdict
from transkribusConnect import *
import argparse
import getpass
import re
import requests
import pprint as pp


def login_process(args):
    password = getpass.getpass()
    logindata = login(args.user, password)
    logindata = logindata.replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "")
    data = et.fromstring(logindata)
    return data


def filter_collections(args, colls):
    if args.coll is not None:
        defined_collections = args.coll.split(",")
    valid_collections = []
    for collection in colls:
        if args.coll is not None:
            if str(collection["colId"]) in defined_collections or any([re.match(c, collection["colName"]) for c in defined_collections]):
                valid_collections.append((collection["colName"], str(collection["colId"])))
        else:
            valid_collections.append((collection["colName"], str(collection["colId"])))
    
    print("The following collections will be processed:")
    for colName, colId in valid_collections:
        print(colId + "\t" + colName)
        
    return valid_collections


def filter_documents(args, colls, sid):
    if args.doc is not None:
        defined_documents = args.doc.split(",")
    valid_documents = []
    for colName, colId in colls:
        documents = getDocuments(sid, colId)
        for document in documents:
            if args.doc is not None:
                if str(document["docId"]) in defined_documents or any([re.match(c, document["title"]) for c in defined_documents]):
                    valid_documents.append((str(document["docId"]), document["title"], colId))
            else:
                valid_documents.append((str(document["docId"]), document["title"], colId))
                
    print("The following documents will be processed:")
    for docId, title, colId in valid_documents:
        print(docId + "\t" + title)
    
    return valid_documents


# left column are the tags the tagger assigns
# right column is how they should be called in Transkribus
# all tags in the right column will be overwritten when processing a page
TAG_CONVERSION = {
    "PER": "person",
    "ORG": "organization",
    "LOC": "place"
}


def process_page(url, tagger, debug):
    """
    Note that this part of the script will probably need some customizing for each user, for example how to handle tags that cross lines or if text should be processed on page-level or textregion-level.
    """
    r = requests.get(url)
    if r.status_code == requests.codes.ok:
        content = r.text
    else:
        print("Requesting xml from transkribus failed ({})".format(url))
        return
    content = content.replace('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "")
    root = et.fromstring(content)
    # get all text elements
    texts = root.findall(".//{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextLine/{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextEquiv/{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}Unicode")
    # construct a single string as input for the tagger
    text = " ".join([re.sub("(¬|-)$", "¬", t.text) for t in texts if t.text is not None]).replace("¬ ", "")
    # annotate text
    text = Sentence(text)
    tagger.predict(text)
    
    if debug:
        for label in text.get_labels():
            print(label)
    
    textlines = root.findall(".//{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextLine")
    current_index = 0
    continued = []
    for textline in textlines:
        unicode = textline.find("./{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}TextEquiv/{http://schema.primaresearch.org/PAGE/gts/pagecontent/2013-07-15}Unicode")
        
        if unicode.text is None:  # empty line of text
            continue

        line_length = len(unicode.text)

        # we need to correct for line ending signs because they get deleted when tagging
        # correction is done by 2 instead of by 1 because a space is deleted as well
        if unicode.text.endswith("-") or unicode.text.endswith("¬"):
            line_length -= 2

        # get line attributes
        attribute_list = []
        attributes = textline.get("custom")
        attributes = re.findall(r"(\w+) {(.*?)}", attributes)
        for att_type, att_att in attributes:
            # remove old tags
            if att_type in TAG_CONVERSION.values():
                continue
            att_att = re.findall(r"(\w+?):(.+?);", att_att)
            attribute_list.append({"placeholder_type": att_type, "attr": dict(att_att)})

        # add tags that have started on the line before and continue here
        new_continued = []
        for cont in continued:
            # catch if a tag flows over more than 2 lines
            if cont[1] > line_length:
                new_continued.append((cont[0], cont[1] - line_length - 1))
                corrected_label_length = cont[1]
                if unicode.text.endswith("-") or unicode.text.endswith("¬"):
                    corrected_label_length += 2
                attribute_list.append({"placeholder_type": cont[0], "attr": {"offset": "0", "length": corrected_label_length, "continued":"true"}})
            else:
                attribute_list.append({"placeholder_type": cont[0], "attr": {"offset": "0", "length": cont[1], "continued":"true"}})
        continued = new_continued

        # collect assigned labels for this line
        for label in text.get_labels():
            # only assign labels which are in the defined dictionary
            if label.value not in TAG_CONVERSION:
                continue
            label_type = TAG_CONVERSION[label.value]
            # check if the label starts on this line
            if label.data_point.start_position >= current_index and label.data_point.start_position < current_index + line_length:
                # convert original label indices to line relative indices
                label_on_line_start = label.data_point.start_position - current_index
                label_length = label.data_point.end_position - label.data_point.start_position
                # check if label overflows and reaches next line as well
                if label_on_line_start + label_length > line_length:
                    continued.append((label_type, (label_on_line_start + label_length) - line_length - 1))  # remaining length -1 for the space that separates the text
                    corrected_label_length = line_length - label_on_line_start
                    if unicode.text.endswith("-") or unicode.text.endswith("¬"):
                        corrected_label_length += 2
                    attribute_list.append({"placeholder_type": label_type, "attr": {"offset": label_on_line_start, "length": corrected_label_length, "continued":"true"}})
                else:
                    attribute_list.append({"placeholder_type": label_type, "attr": {"offset": label_on_line_start, "length": label_length}})

        current_index += line_length + 1  # +1 for the space that separates the lines in the text

        # write modified line attributes
        new_attributes = []
        for att in attribute_list:
            construct_information = []
            for subatt, subatt_value in att["attr"].items():
                construct_information.append("{}:{};".format(subatt, subatt_value))
            info = " ".join(construct_information)
            new_attributes.append("{0} {{{1}}}".format(att["placeholder_type"], info))
        new_attributes = " ".join(new_attributes)
        textline.set("custom", new_attributes)
    return root
    
            
def main():
    parser = argparse.ArgumentParser(description='Access Transkribus documents via API, annotate them, then upload the annotated documents.')
    parser.add_argument('-u', '--user', help='Transkribus username. Required.', required=True)
    parser.add_argument('-m', '--model', help='Enter path to model to use. Uses flair syntax, which means you can directly access models hosted on huggingface this way. Required.', required=True)
    parser.add_argument('-c', '--coll', default=None, help='Collection IDs or regex expression of collection names, multiple collections can be entered by separating by a comma. Omitting this will process all collections accessible to the user.')
    parser.add_argument('-d', '--doc', default=None, help='Document IDs or regex expression of document names, multiple documents can be entered by separating by a comma. Omitting this will process all documents accessible to the user in the defined collections.')
    parser.add_argument('-p', '--pages', default=None, help='Enter single integers or a range of pages, e.g. "3-42". You can also enter multiple ranges or numbers by separating them by a comma. Only really useful if you\'re processing a single document, but whatever floats your boat.')
    parser.add_argument('-s', '--status', default=None, help='Which version of the document should be annotated? Default will use the latest version, but you can instead enter any status you might prefer like "Ground Truth" or "Final". If multiple versions of the given status exist for the document, only the newest version will be processed. Mind you that any documents that do not contain a version with the defined status will not be processed.')
    parser.add_argument('--comment', default="Automated NER", help='Pass a custom comment which will be visible in Transkribus in the "Message" column. E.g. use to note which NER model was used.')
    parser.add_argument('--debug', action="store_true", default=False, help='Get some additional info for debugging purposes.')
    
    args = parser.parse_args()
    
    data = login_process(args)
    
    sid = data.find("sessionId").text
    colls = getCollections(sid)
    
    colls = filter_collections(args, colls)
    
    docs = filter_documents(args, colls, sid)
    
    if args.pages is not None:
        all_pageranges = []
        pageranges = args.pages.split(",")
        for pagerange in pageranges:
            pagerange = pagerange.split("-")
            all_pageranges.append([int(pr) for pr in pagerange])
            
    tagger = SequenceTagger.load(args.model)
    
    for docId, docName, colId in docs:
        docInfo = getDocumentR(colId, docId, sid)
        pages = docInfo["pageList"]["pages"]
        for page in pages:
            pageNo = page["pageNr"]
            if args.pages is not None:
                valid = False
                for pr in all_pageranges:
                    if len(pr) == 1:
                        if pr[0] == pageNo:
                            valid = True
                            break
                    elif len(pr) == 2:
                        if pageNo >= pr[0] and pageNo <= pr[1]:
                            valid = True
                            break
                if not valid:
                    continue
            versions = page["tsList"]["transcripts"]
            version = None
            if args.status is None:
                version = versions[0]  # should be always the latest
            else:
                for ver in versions:
                    if ver["status"] == args.status:
                        version = ver
                        break
            if version is not None:
                print("Processing {}, page {}...".format(docName, pageNo))
                modified_xml = process_page(version["url"], tagger, args.debug)
                #pp.pprint(et.tostring(modified_xml).decode("utf8"))
                r = postPage(colId, docId, str(pageNo), sid, et.tostring(modified_xml), args.comment)
                if r:
                    print("Modified XML successfully uploaded.")
    
    
    
    
        

if __name__ == "__main__":
    main()