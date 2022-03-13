import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path
from string import Template

from musicxml.generate_classes.utils import musicxml_xsd_et_root
from musicxml.util.core import convert_to_xsd_class_name
from musicxml.xsd.xsdtree import XSDTree, XSD_TREE_DICT

default_path = Path(__file__).parent / 'defaults' / 'xsdindicator.py'
target_path = Path(__file__).parent.parent / 'xsd' / 'xsdindicator.py'

template_string = """
class $class_name($base_classes):
    \"\"\"$doc\"\"\"
    
    XSD_TREE = XSD_TREE_DICT['group']['$name']
"""

xsd_indicator_class_names = ['XSDSequence', 'XSDChoice', 'XSDGroup']


def group_indicator_class_as_string(group_indicator):
    name = group_indicator[0]
    xsd_tree = group_indicator[1]
    class_name = xsd_tree.xsd_element_class_name
    xsd_indicator_class_names.append(class_name)
    base_classes = ('XSDGroup',)
    doc = xsd_tree.get_doc()
    if not doc:
        doc = ""
    t = Template(template_string).substitute(class_name=class_name, base_classes=', '.join(base_classes), doc=doc, name=name)
    return t


all_xsd_group_et_elements = XSD_TREE_DICT['group']

with open(target_path, 'w+') as f:
    with open(default_path, 'r') as default:
        with redirect_stdout(f):
            print(default.read())
    with redirect_stdout(f):
        for group in all_xsd_group_et_elements.items():
            print(group_indicator_class_as_string(group))
        print(f'__all__={xsd_indicator_class_names}')
