import xml.etree.ElementTree as ET

from musicxml.generate_classes.utils import musicxml_xsd_et_root, ns
from musicxml.xmlelement.core import XMLElement
from musicxml.xsd.xsdcomplextype import *
from musicxml.xsd.xsdsimpletype import *
from musicxml.xsd.xsdtree import XSDTree

# xml score partwise
xsd_tree_score_partwise_part = XSDTree(musicxml_xsd_et_root.find(f".//{ns}element[@name='score-partwise']"))


class XMLScorePartwise(XMLElement):
    TYPE = XSDComplexTypeScorePartwise
    XSD_TREE = XSDTree(musicxml_xsd_et_root.find(f".//{ns}element[@name='score-partwise']"))

    def write(self, path, intelligent_choice=False):
        with open(path, 'w') as file:
            file.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
            file.write(self.to_string(intelligent_choice=intelligent_choice))

    @property
    def __doc__(self):
        return self.XSD_TREE.get_doc()


class XMLPart(XMLElement):
    TYPE = XSDComplexTypePart
    XSD_TREE = XSDTree(musicxml_xsd_et_root.findall(f".//{ns}element[@name='score-partwise']//{ns}element")[0])

    @property
    def __doc__(self):
        return self.XSD_TREE.get_doc()


class XMLMeasure(XMLElement):
    TYPE = XSDComplexTypeMeasure
    XSD_TREE = XSDTree(musicxml_xsd_et_root.findall(f".//{ns}element[@name='score-partwise']//{ns}element")[1])

    @property
    def __doc__(self):
        return self.XSD_TREE.get_doc()


class XMLDirective(XMLElement):
    TYPE = XSDComplexTypeDirective
    XSD_TREE = XSDTree(musicxml_xsd_et_root.find(".//{*}complexType[@name='attributes']//{*}element[@name='directive']"))

    @property
    def __doc__(self):
        return self.XSD_TREE.get_doc()
# -----------------------------------------------------
# AUTOMATICALLY GENERATED WITH generate_xml_elements.py
# -----------------------------------------------------
