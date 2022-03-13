from contextlib import redirect_stdout
from pathlib import Path
from string import Template
import xml.etree.ElementTree as ET

from musicxml.generate_classes.utils import xml_xsd_et_root, musicxml_xsd_et_root, get_simple_type_all_base_classes
from musicxml.xsd.xsdtree import XSDTree, XSD_TREE_DICT

default_path_1 = Path(__file__).parent / 'defaults' / 'xsdsimpletype1.py'
default_path_2 = Path(__file__).parent / 'defaults' / 'xsdsimpletype2.py'
target_path = Path(__file__).parent.parent / 'xsd' / 'xsdsimpletype.py'

template_string = """
class $class_name($base_classes):
    \"\"\"$doc\"\"\"
    _XSD_TREE = XSD_TREE_DICT['simpleType']['$name']
"""

xsd_simple_types = ['XSDSimpleType', 'XSDSimpleTypeInteger', 'XSDSimpleTypeNonNegativeInteger', 'XSDSimpleTypePositiveInteger',
                    'XSDSimpleTypeDecimal', 'XSDSimpleTypeString', 'XSDSimpleTypeToken', 'XSDSimpleTypeDate',
                    'XSDSimpleTypeNumberOrNormal', 'XSDSimpleTypePositiveIntegerOrEmpty', 'XSDSimpleTypeFontSize',
                    'XSDSimpleTypeYesNoNumber']


def simple_type_class_as_string(simple_type_):
    xsd_tree = simple_type_[1]
    name = simple_type_[0]
    class_name = xsd_tree.xsd_element_class_name
    xsd_simple_types.append(class_name)
    base_classes = get_simple_type_all_base_classes(xsd_tree)
    doc = xsd_tree.get_doc()
    if not doc:
        doc = ""
    t = Template(template_string).substitute(class_name=class_name, base_classes=', '.join(base_classes), doc=doc, name=name)
    return t


all_simple_type_et_elements = XSD_TREE_DICT['simpleType']
simple_type_elements = [item for item in all_simple_type_et_elements.items() if item[0] not in ['yes-no-number', 'font-size',
                                                                                                'number-or-normal',
                                                                                                'positive-integer-or-empty']]
with open(target_path, 'w+') as f:
    with open(default_path_1, 'r') as default_1:
        with redirect_stdout(f):
            print(default_1.read())
    with redirect_stdout(f):
        for simple_type in simple_type_elements:
            print(simple_type_class_as_string(simple_type))
    with open(default_path_2, 'r') as default_2:
        with redirect_stdout(f):
            print(default_2.read())
            print(f'__all__={xsd_simple_types}')
