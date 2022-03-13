from contextlib import redirect_stdout
from pathlib import Path
from string import Template
import xml.etree.ElementTree as ET

from musicxml.generate_classes.utils import get_all_et_elements
from musicxml.xsd.xsdtree import XSDTree, XSD_TREE_DICT

sources_path = Path(__file__).parent / 'musicxml_4_0.xsd'
default_path = Path(__file__).parent / 'defaults' / 'xsdattribute.py'
target_path = Path(__file__).parent.parent / 'xsd' / 'xsdattribute.py'

template_string = """
class $class_name($base_classes):
    \"\"\"
    $doc
    \"\"\"
    XSD_TREE = XSD_TREE_DICT['attributeGroup']['$name']
"""

xsd_attribute_class_names = ['XSDAttribute', 'XSDAttributeGroup']


def attribute_group_class_as_string(attribute_group):
    name = attribute_group[0]
    xsd_tree = attribute_group[1]
    class_name = xsd_tree.xsd_element_class_name
    xsd_attribute_class_names.append(class_name)
    base_classes = ('XSDAttributeGroup',)
    doc = xsd_tree.get_doc()
    if not doc:
        doc = ""
    t = Template(template_string).substitute(class_name=class_name, base_classes=', '.join(base_classes), doc=doc, name=name)
    return t


all_attribute_group_et_elements = XSD_TREE_DICT['attributeGroup']

with open(target_path, 'w+') as f:
    with open(default_path, 'r') as default:
        with redirect_stdout(f):
            print(default.read())
    with redirect_stdout(f):
        for attribute_group in all_attribute_group_et_elements.items():
            print(attribute_group_class_as_string(attribute_group))
        print(f'__all__={xsd_attribute_class_names}')
