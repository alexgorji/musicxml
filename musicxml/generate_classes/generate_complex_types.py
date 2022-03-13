import copy
from contextlib import redirect_stdout
from pathlib import Path
from string import Template
import xml.etree.ElementTree as ET

from musicxml.generate_classes.utils import get_complex_type_all_base_classes, get_all_et_elements, musicxml_xsd_et_root
from musicxml.xsd.xsdtree import XSDTree, XSD_TREE_DICT
from musicxml.xsd.xsdsimpletype import *

sources_path = Path(__file__).parent / 'musicxml_4_0.xsd'
default_path = Path(__file__).parent / 'defaults' / 'xsdcomplextype.py'
target_path = Path(__file__).parent.parent / 'xsd' / 'xsdcomplextype.py'

template_string = """
class $class_name($base_classes):
    \"\"\"$doc\"\"\"
    
    _SIMPLE_CONTENT = $simple_content
    _XSD_TREE = XSD_TREE_DICT['complexType']['$name']
"""

xsd_complex_types = ['XSDComplexType', 'XSDComplexTypeScorePartwise', 'XSDComplexTypePart', 'XSDComplexTypeMeasure',
                     'XSDComplexTypeDirective', 'XSDComplexTypeNote']


def complex_type_class_as_string(complex_type):
    def get_doc():
        output = xsd_tree.get_doc()
        if simple_content:
            simple_doc = eval(simple_content).get_xsd_tree().get_doc()
            if simple_doc and simple_doc != "":
                if output and output != "":
                    output += '\n'
                    output += '\n'
                output += '``simpleContent``: '
                output += simple_doc
        if not output:
            output = ""
        return output

    name = complex_type[0]
    xsd_tree = complex_type[1]
    class_name = xsd_tree.xsd_element_class_name
    xsd_complex_types.append(class_name)
    base_class_names = []
    simple_content = None
    for cls_name in get_complex_type_all_base_classes(xsd_tree):
        if cls_name.startswith('XSDSimpleType'):
            if simple_content is not None:
                raise NotImplementedError('More than one Simple Type as base class.')
            simple_content = cls_name
        else:
            base_class_names.append(cls_name)

    t = Template(template_string).substitute(class_name=class_name, base_classes=', '.join(base_class_names), simple_content=simple_content,
                                             doc=get_doc(), name=name)
    return t


# all_complex_type_et_elements = [ct for ct in get_all_et_elements(sources_path, 'complexType') if ct.attrib['name'] != 'note']

# all_complex_type_names = [ct.attrib.get('name') for ct in musicxml_xsd_et_root.findall(
#     f".//{{*}}complexType") if ct.attrib.get('name')]

# all_complex_type_names.remove('note')

all_complex_type_et_elements = XSD_TREE_DICT['complexType'].copy()
all_complex_type_et_elements.pop('note')

with open(target_path, 'w+') as f:
    with open(default_path, 'r') as default:
        with redirect_stdout(f):
            print(default.read())
    with redirect_stdout(f):
        for complex_type in all_complex_type_et_elements.items():
            print(complex_type_class_as_string(complex_type))
        print(f'__all__={xsd_complex_types}')
