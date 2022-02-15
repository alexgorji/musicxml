import copy
import xml.etree.ElementTree as ET
from typing import Optional, List, Callable, Union

from musicxml.exceptions import XSDWrongAttribute, XSDAttributeRequiredException, XMLElementChildrenRequired
from musicxml.generate_classes.utils import musicxml_xsd_et_root, ns
from musicxml.tree.tree import Tree
from musicxml.util.core import cap_first, replace_key_underline_with_hyphen
from musicxml.xmlelement.containers import containers
from musicxml.xmlelement.exceptions import XMLElementCannotHaveChildrenError
from musicxml.xmlelement.xmlchildcontainer import DuplicationXSDSequence
from musicxml.xsd.xsdcomplextype import *
from musicxml.xsd.xsdsimpletype import *
from musicxml.xsd.xsdtree import XSDTree


class XMLElement(Tree):
    PROPERTIES = {'compact_repr', 'is_leaf', 'level', 'attributes', 'child_container_tree', 'possible_children_names',
                  'et_xml_element', 'name', 'type_', 'value_', 'parent_xsd_element'}
    TYPE = None
    XSD_TREE: Optional[XSDTree] = None

    def __init__(self, value_=None, **kwargs):
        self._type = None
        super().__init__()
        self._value_ = None
        self._attributes = {}
        self._et_xml_element = None
        self._child_container_tree = None
        self._unordered_children = []
        self.value_ = value_
        self._set_attributes(kwargs)

        self._create_child_container_tree()

    def _check_attribute(self, name, value):
        attributes = self.TYPE.get_xsd_attributes()
        allowed_attributes = [attribute.name for attribute in attributes]
        if name not in [attribute.name for attribute in self.TYPE.get_xsd_attributes()]:
            raise XSDWrongAttribute(f"{self.__class__.__name__} has no attribute {name}. Allowed attributes are: {allowed_attributes}")
        for attribute in attributes:
            if attribute.name == name:
                return attribute(value)

    def _check_child_to_be_added(self, child):
        if not isinstance(child, XMLElement):
            raise TypeError

    def _check_required_attributes(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            required_attributes = [attribute for attribute in self.TYPE.get_xsd_attributes() if attribute.is_required]
            for required_attribute in required_attributes:
                if required_attribute.name not in self.attributes:
                    raise XSDAttributeRequiredException(f"{self.__class__.__name__} requires attribute: {required_attribute.name}")

    def _check_required_value(self):
        if self.TYPE.XSD_TREE.is_simple_type and self.value_ is None:
            raise ValueError(f"{self.__class__.__name__} needs a value.")

    def _convert_attribute_to_child(self, name, value):
        if not name.startswith('xml_'):
            raise NameError
        child_name = name.replace('xml_', '')

        if '-'.join(child_name.split('_')) not in self.possible_children_names:
            raise NameError

        child_class_name = 'XML' + ''.join([cap_first(partial) for partial in child_name.split('_')])
        child_class = eval(child_class_name)

        found_child = self.find_child(child_class_name)
        if isinstance(value, child_class):
            if found_child:
                self.replace_child(found_child, value)
            else:
                self.add_child(value)
        elif value is None:
            if found_child:
                self.remove(found_child)
        else:
            if found_child:
                found_child.value_ = value
            else:
                self.add_child(child_class(value))

    def _create_child_container_tree(self):
        try:
            if self.TYPE.XSD_TREE.is_complex_type:
                self._child_container_tree = copy.copy(containers[self.TYPE.__name__])
                self._child_container_tree._parent_xml_element = self
        except KeyError:
            pass

    def _create_et_xml_element(self):
        self._et_xml_element = ET.Element(self.name, {k: str(v) for k, v in self.attributes.items()})
        if self.value_ is not None:
            self._et_xml_element.text = str(self.value_)
        for child in self.get_children():
            self._et_xml_element.append(child.et_xml_element)
        ET.indent(self._et_xml_element, space="  ", level=self.level)

    def _final_checks(self, intelligent_choice=False):
        self._check_required_value()
        if self._child_container_tree:
            required_children = self._child_container_tree.get_required_element_names(intelligent_choice=intelligent_choice)
            if required_children:
                raise XMLElementChildrenRequired(f"{self.__class__.__name__} requires at least following children: {required_children}")

        self._check_required_attributes()

        for child in self.get_children():
            child._final_checks(intelligent_choice=intelligent_choice)

    def _get_attributes_error_message(self, wrong_name):
        attributes = self.TYPE.get_xsd_attributes()
        allowed_attributes = [attribute.name for attribute in attributes]
        return f"{self.__class__.__name__} has no attribute {wrong_name}. Allowed attributes are: " \
               f"{sorted(allowed_attributes)} or possible " \
               f"children as attributes: {sorted(['xml_' + '_'.join(ch.split('-')) for ch in self.possible_children_names])}"

    def _set_attributes(self, val):
        if val is None:
            return

        if self.TYPE.XSD_TREE.is_simple_type:
            if val:
                raise XSDWrongAttribute(f'{self.__class__.__name__} has no attributes.')

        elif not isinstance(val, dict):
            raise TypeError

        new_attributes = replace_key_underline_with_hyphen(dict_=val)
        none_values_dict = {k: v for k, v in new_attributes.items() if v is None}
        for key in none_values_dict:
            new_attributes.pop(key)
            try:
                self.attributes.pop(key)
            except KeyError:
                pass
        for key in new_attributes:
            self._check_attribute(key, new_attributes[key])
        self._attributes = {**self._attributes, **new_attributes}

    @property
    def attributes(self):
        """
        :return: a dictionary of attributes like {'font-family': 'Arial'} if XMLElement.font_family is set to Arial. The attributes will
        appear in the main xml tag: <text font-family="Arial">hello</text>.
        """
        return self._attributes

    @property
    def child_container_tree(self):
        """
        :return: A ChildContainerTree object which is used to manage and control XMLElements children. The nodes of a ChildContainerTree
        have a core content property of types XSDSequence, XSDChoice, XSDGroup or XSDElement. XSDElement are the content type of
        ChildContainerTree leaves where one or more XMLElements of a single type (depending on maxOccur attribute of element) can be
        added to its xml_elements list. An interaction of xsd indicators (sequence, choice and group) with xsd elements makes it possible to
        add XMLElement's Children in the right order and control all xsd rules which apply to musicxml. A variety of exceptions help user to
        control the xml structure of the exported file which they are intending to use as a musicxml format file.
        """
        return self._child_container_tree

    @property
    def et_xml_element(self):
        """
        :return:  A xml.etree.ElementTree.Element which is used to write the musicxml file.
        """
        self._create_et_xml_element()
        return self._et_xml_element

    @property
    def name(self):
        return self.XSD_TREE.get_attributes()['name']

    @property
    def possible_children_names(self):
        if not self.child_container_tree:
            return {}
        else:
            return {leaf.content.name for leaf in self.child_container_tree.iterate_leaves()}

    @property
    def value_(self):
        """
        :return: A validated value of XMLElement which will be translated to its text in xml format.
        """
        return self._value

    @value_.setter
    def value_(self, val):
        """
        :param val: Value to be validated and added to XMLElement. This value will be translated to xml element's text in xml format.
        """
        self.TYPE(val, parent=self)
        self._value = val

    @classmethod
    def get_xsd(cls):
        """
        :return: Snippet of musicxml xsd file which is relevant for this XMLElement.
        """
        return cls.XSD_TREE.get_xsd()

    def add_child(self, child: 'XMLElement', forward: Optional[int] = None) -> 'XMLElement':
        """
        :param XMLElement child: XMLElement child to be added to XMLElement's ChildContainerTree and _unordered_children.
        :param int forward: If there are more than one XSDElement leaves in self.child_container_tree, forward can be used to determine
        manually which of these equivocal xsd elements is going to be used to attach the child.
        :return: Added child.
        """
        if not self._child_container_tree:
            raise XMLElementCannotHaveChildrenError()
        self._child_container_tree.add_element(child, forward)
        self._unordered_children.append(child)
        child._parent = self
        return child

    def get_children(self, ordered: bool = True) -> List['XMLElement']:
        """
        :param bool ordered: True or False.
        :return: XMLElement added children. If ordered is False the _unordered_children is returned as a more light weighted way of
        getting children instead of using the leaves of ChildContainerTree.
        """
        if ordered is False:
            return self._unordered_children
        if self._child_container_tree:
            return [xml_element for leaf in self._child_container_tree.iterate_leaves() for xml_element in leaf.content.xml_elements if
                    leaf.content.xml_elements]
        else:
            return []

    def find_child(self, name: Union['XMLElement', str], ordered: bool = False) -> 'XMLElement':
        """
        :param XMLElement/String name: Child or it's name as string.
        :param bool ordered: get_children mode to be used to find first appearance of child.
        :return: found child.
        """
        if isinstance(name, type):
            name = name.__name__
        for ch in self.get_children(ordered=ordered):
            if ch.__class__.__name__ == name:
                return ch

    def find_children(self, name: Union['XMLElement', str], ordered: bool = False) -> List['XMLElement']:
        """
        :param XMLElement/String name: Child or it's name as string.
        :param bool ordered: get_children mode to be used to find children.
        :return: found children.
        """
        if isinstance(name, type):
            name = name.__name__
        return [ch for ch in self.get_children(ordered=ordered) if ch.__class__.__name__ == name]

    def remove(self, child: 'XMLElement') -> None:
        """
        :param XMLElement child: child to be removed. This method must be used to remove a child properly from ChildContainerTree and
        reset its behaviour.
        :return: None
        """

        def remove_duplictation():
            for node in parent_container.reversed_path_to_root():
                if node.up:
                    if isinstance(node.up.content, DuplicationXSDSequence) and len(node.up.get_children()) > 1:
                        remove_duplicate = False
                        for leaf in node.iterate_leaves():
                            if leaf != parent_container and leaf.content.xml_elements:
                                break
                            remove_duplicate = True
                        if remove_duplicate:
                            node.up.remove(node)

        self._unordered_children.remove(child)

        parent_container = child.parent_xsd_element.parent_container.get_parent()
        if parent_container.chosen_child == child.parent_xsd_element.parent_container:
            parent_container.chosen_child = None
            parent_container.requirements_not_fulfilled = True

        child.parent_xsd_element.xml_elements.remove(child)
        child.parent_xsd_element = None
        child._parent = None
        del child
        remove_duplictation()

    def replace_child(self, old: Union['XMLElement', Callable], new: 'XMLElement', index: int = 0) -> None:
        """
        :param XMLElement or function old: A child or function which is used to find a child to be replaced.
        :param XMLElement new: child to be replaced with.
        :param int index: index of old in list of old appearances
        :return: None
        """
        if hasattr(old, '__call__'):
            list_of_olds = [ch for ch in self.get_children(ordered=True) if old(ch)]
        else:
            list_of_olds = [ch for ch in self.get_children(ordered=True) if ch == old]

        if not list_of_olds:
            raise ValueError(f"{old} not in list.")
        self._check_child_to_be_added(new)
        old_index = self._unordered_children.index(list_of_olds[index])
        old_child = self._unordered_children[old_index]
        self._unordered_children.remove(old_child)
        self._unordered_children.insert(old_index, new)

        parent_xsd_element = old_child.parent_xsd_element
        new.parent_xsd_element = parent_xsd_element
        parent_xsd_element._xml_elements = [new if el == old_child else el for el in parent_xsd_element.xml_elements]
        new._parent = self
        old._parent = None

    def to_string(self, intelligent_choice: bool = False) -> str:
        """
        :param bool intelligent_choice: Set to True if you wish to use intelligent choice in final checks to be able to change the
        attachment order of XMLElement children in self.child_container_tree if an Exception was thrown and other choices can still be
        checked. (No GUARANTEE!)
        :return: String in xml format.
        """
        self._final_checks(intelligent_choice=intelligent_choice)
        self._create_et_xml_element()

        return ET.tostring(self.et_xml_element, encoding='unicode') + '\n'

    def __setattr__(self, key, value):
        if key[0] == '_' or key in self.PROPERTIES:
            super().__setattr__(key, value)
        elif key.startswith('xml_'):
            try:
                self._convert_attribute_to_child(name=key, value=value)
            except NameError:
                raise AttributeError(self._get_attributes_error_message(key))
        else:
            try:
                self._set_attributes({key: value})
            except XSDWrongAttribute:
                raise AttributeError(self._get_attributes_error_message(key))

    def __getattr__(self, item):
        try:
            return self.attributes['-'.join(item.split('_'))]
        except KeyError:
            attributes = self.TYPE.get_xsd_attributes()
            allowed_attributes = ['_'.join(attribute.name.split('-')) for attribute in attributes]
            if item in allowed_attributes:
                return None
            else:
                if item.startswith('xml'):
                    child_name = item.replace('xml_', '')
                    for child in self.get_children(ordered=False):
                        if child.name == '-'.join(child_name.split('_')):
                            return child
                    if '-'.join(child_name.split('_')) in self.possible_children_names:
                        return None
                raise AttributeError(self._get_attributes_error_message(item))


# xml score partwise
xsd_tree_score_partwise_part = XSDTree(musicxml_xsd_et_root.find(f".//{ns}element[@name='score-partwise']"))
"""
<xs:element name="score-partwise" block="extension substitution" final="#all">
    <xs:annotation>
        <xs:documentation>The score-partwise element is the root element for a partwise MusicXML score. It includes a score-header group followed by a series of parts with measures inside. The document-attributes attribute group includes the version attribute.</xs:documentation>
    </xs:annotation>
    <xs:complexType>
        <xs:sequence>
            <xs:group ref="score-header"/>
            <xs:element name="part" maxOccurs="unbounded">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="measure" maxOccurs="unbounded">
                            <xs:complexType>
                                <xs:group ref="music-data"/>
                                <xs:attributeGroup ref="measure-attributes"/>
                            </xs:complexType>
                        </xs:element>
                    </xs:sequence>
                    <xs:attributeGroup ref="part-attributes"/>
                </xs:complexType>
            </xs:element>
        </xs:sequence>
        <xs:attributeGroup ref="document-attributes"/>
    </xs:complexType>
</xs:element>
"""


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


class XMLP(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="p" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPpp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ppp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPppp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pppp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPpppp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ppppp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPppppp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pppppp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLF(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="f" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFf(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ff" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFff(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fff" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFfff(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ffff" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFffff(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fffff" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFfffff(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ffffff" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="mp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMf(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="mf" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSf(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sf" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSfp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sfp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSfpp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sfpp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRf(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="rf" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRfz(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="rfz" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSfz(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sfz" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSffz(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sffz" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFz(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fz" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLN(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="n" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPf(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pf" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSfzp(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sfzp" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherDynamics(XMLElement):
    
    TYPE = XSDComplexTypeOtherText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-dynamics" type="other-text" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiChannel(XMLElement):
    
    TYPE = XSDSimpleTypeMidi16
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-channel" type="midi-16" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The midi-channel element specifies a MIDI 1.0 channel numbers ranging from 1 to 16.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiName(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-name" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The midi-name element corresponds to a ProgramName meta-event within a Standard MIDI File.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiBank(XMLElement):
    
    TYPE = XSDSimpleTypeMidi16384
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-bank" type="midi-16384" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The midi-bank element specifies a MIDI 1.0 bank number ranging from 1 to 16,384.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiProgram(XMLElement):
    
    TYPE = XSDSimpleTypeMidi128
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-program" type="midi-128" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The midi-program element specifies a MIDI 1.0 program number ranging from 1 to 128.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiUnpitched(XMLElement):
    
    TYPE = XSDSimpleTypeMidi128
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-unpitched" type="midi-128" minOccurs="0">
    <xs:annotation>
        <xs:documentation>For unpitched instruments, the midi-unpitched element specifies a MIDI 1.0 note number ranging from 1 to 128. It is usually used with MIDI banks for percussion. Note that MIDI 1.0 note numbers are generally specified from 0 to 127 rather than the 1 to 128 numbering used in this element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVolume(XMLElement):
    
    TYPE = XSDSimpleTypePercent
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="volume" type="percent" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The volume element value is a percentage of the maximum ranging from 0 to 100, with decimal values allowed. This corresponds to a scaling value for the MIDI 1.0 channel volume controller.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPan(XMLElement):
    
    TYPE = XSDSimpleTypeRotationDegrees
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pan" type="rotation-degrees" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The pan and elevation elements allow placing of sound in a 3-D space relative to the listener. Both are expressed in degrees ranging from -180 to 180. For pan, 0 is straight ahead, -90 is hard left, 90 is hard right, and -180 and 180 are directly behind the listener.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLElevation(XMLElement):
    
    TYPE = XSDSimpleTypeRotationDegrees
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="elevation" type="rotation-degrees" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The elevation and pan elements allow placing of sound in a 3-D space relative to the listener. Both are expressed in degrees ranging from -180 to 180. For elevation, 0 is level with the listener, 90 is directly above, and -90 is directly below.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDisplayText(XMLElement):
    
    TYPE = XSDComplexTypeFormattedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="display-text" type="formatted-text" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccidentalText(XMLElement):
    
    TYPE = XSDComplexTypeAccidentalText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accidental-text" type="accidental-text" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLIpa(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ipa" type="xs:string">
    <xs:annotation>
        <xs:documentation>The ipa element represents International Phonetic Alphabet (IPA) sounds for vocal music. String content is limited to IPA 2015 symbols represented in Unicode 13.0.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMute(XMLElement):
    
    TYPE = XSDSimpleTypeMute
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="mute" type="mute" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSemiPitched(XMLElement):
    
    TYPE = XSDSimpleTypeSemiPitched
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="semi-pitched" type="semi-pitched" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherPlay(XMLElement):
    
    TYPE = XSDComplexTypeOtherPlay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-play" type="other-play" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDivisions(XMLElement):
    
    TYPE = XSDSimpleTypePositiveDivisions
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="divisions" type="positive-divisions" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Musical notation duration is commonly represented as fractions. The divisions element indicates how many divisions per quarter note are used to indicate a note's duration. For example, if duration = 1 and divisions = 2, this is an eighth note duration. Duration and divisions are used directly for generating sound output, so they must be chosen to take tuplets into account. Using a divisions element lets us use just one number to represent a duration for each note in the score, while retaining the full power of a fractional representation. If maximum compatibility with Standard MIDI 1.0 files is important, do not have the divisions value exceed 16383.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKey(XMLElement):
    
    TYPE = XSDComplexTypeKey
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="key" type="key" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The key element represents a key signature. Both traditional and non-traditional key signatures are supported. The optional number attribute refers to staff numbers. If absent, the key signature applies to all staves in the part.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTime(XMLElement):
    
    TYPE = XSDComplexTypeTime
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="time" type="time" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>Time signatures are represented by the beats element for the numerator and the beat-type element for the denominator.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaves(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staves" type="xs:nonNegativeInteger" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The staves element is used if there is more than one staff represented in the given part (e.g., 2 staves for typical piano parts). If absent, a value of 1 is assumed. Staves are ordered from top to bottom in a part in numerical order, with staff 1 above staff 2.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartSymbol(XMLElement):
    
    TYPE = XSDComplexTypePartSymbol
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-symbol" type="part-symbol" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The part-symbol element indicates how a symbol for a multi-staff part is indicated in the score.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstruments(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instruments" type="xs:nonNegativeInteger" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The instruments element is only used if more than one instrument is represented in the part (e.g., oboe I and II where they play together most of the time). If absent, a value of 1 is assumed.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLClef(XMLElement):
    
    TYPE = XSDComplexTypeClef
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="clef" type="clef" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>Clefs are represented by a combination of sign, line, and clef-octave-change elements.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffDetails(XMLElement):
    
    TYPE = XSDComplexTypeStaffDetails
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-details" type="staff-details" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The staff-details element is used to indicate different types of staves.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTranspose(XMLElement):
    
    TYPE = XSDComplexTypeTranspose
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="transpose" type="transpose" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>If the part is being encoded for a transposing instrument in written vs. concert pitch, the transposition must be encoded in the transpose element using the transpose type.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLForPart(XMLElement):
    
    TYPE = XSDComplexTypeForPart
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="for-part" type="for-part" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The for-part element is used in a concert score to indicate the transposition for a transposed part created from that score. It is only used in score files that contain a concert-score element in the defaults. This allows concert scores with transposed parts to be represented in a single uncompressed MusicXML file.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMeasureStyle(XMLElement):
    
    TYPE = XSDComplexTypeMeasureStyle
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="measure-style" type="measure-style" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>A measure-style indicates a special way to print partial to multiple measures within a part. This includes multiple rests over several measures, repeats of beats, single, or multiple measures, and use of slash notation.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartClef(XMLElement):
    
    TYPE = XSDComplexTypePartClef
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-clef" type="part-clef" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The part-clef element is used for transpositions that also include a change of clef, as for instruments such as bass clarinet.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartTranspose(XMLElement):
    
    TYPE = XSDComplexTypePartTranspose
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-transpose" type="part-transpose">
    <xs:annotation>
        <xs:documentation>The chromatic element in a part-transpose element will usually have a non-zero value, since octave transpositions can be represented in concert scores using the transpose element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTimeRelation(XMLElement):
    
    TYPE = XSDSimpleTypeTimeRelation
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="time-relation" type="time-relation" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKeyOctave(XMLElement):
    
    TYPE = XSDComplexTypeKeyOctave
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="key-octave" type="key-octave" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The optional list of key-octave elements is used to specify in which octave each element of the key signature appears.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMultipleRest(XMLElement):
    
    TYPE = XSDComplexTypeMultipleRest
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="multiple-rest" type="multiple-rest" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMeasureRepeat(XMLElement):
    
    TYPE = XSDComplexTypeMeasureRepeat
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="measure-repeat" type="measure-repeat" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeatRepeat(XMLElement):
    
    TYPE = XSDComplexTypeBeatRepeat
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beat-repeat" type="beat-repeat" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSlash(XMLElement):
    
    TYPE = XSDComplexTypeSlash
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="slash" type="slash" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffType(XMLElement):
    
    TYPE = XSDSimpleTypeStaffType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-type" type="staff-type" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffLines(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-lines" type="xs:nonNegativeInteger">
    <xs:annotation>
        <xs:documentation>The staff-lines element specifies the number of lines and is usually used for a non 5-line staff. If the staff-lines element is present, the appearance of each line may be individually specified with a line-detail element. </xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLineDetail(XMLElement):
    
    TYPE = XSDComplexTypeLineDetail
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="line-detail" type="line-detail" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffTuning(XMLElement):
    
    TYPE = XSDComplexTypeStaffTuning
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-tuning" type="staff-tuning" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCapo(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="capo" type="xs:nonNegativeInteger" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The capo element indicates at which fret a capo should be placed on a fretted instrument. This changes the open tuning of the strings specified by staff-tuning by the specified number of half-steps.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffSize(XMLElement):
    
    TYPE = XSDComplexTypeStaffSize
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-size" type="staff-size" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInterchangeable(XMLElement):
    
    TYPE = XSDComplexTypeInterchangeable
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="interchangeable" type="interchangeable" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSenzaMisura(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="senza-misura" type="xs:string">
    <xs:annotation>
        <xs:documentation>A senza-misura element explicitly indicates that no time signature is present. The optional element content indicates the symbol to be used, if any, such as an X. The time element's symbol attribute is not used when a senza-misura element is present.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBarStyle(XMLElement):
    
    TYPE = XSDComplexTypeBarStyleColor
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bar-style" type="bar-style-color" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWavyLine(XMLElement):
    
    TYPE = XSDComplexTypeWavyLine
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="wavy-line" type="wavy-line" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSegno(XMLElement):
    
    TYPE = XSDComplexTypeSegno
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="segno" type="segno" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCoda(XMLElement):
    
    TYPE = XSDComplexTypeCoda
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="coda" type="coda" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFermata(XMLElement):
    
    TYPE = XSDComplexTypeFermata
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fermata" type="fermata" minOccurs="0" maxOccurs="2" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEnding(XMLElement):
    
    TYPE = XSDComplexTypeEnding
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ending" type="ending" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRepeat(XMLElement):
    
    TYPE = XSDComplexTypeRepeat
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="repeat" type="repeat" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccordionHigh(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accordion-high" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The accordion-high element indicates the presence of a dot in the high (4') section of the registration symbol. This element is omitted if no dot is present.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccordionMiddle(XMLElement):
    
    TYPE = XSDSimpleTypeAccordionMiddle
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accordion-middle" type="accordion-middle" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The accordion-middle element indicates the presence of 1 to 3 dots in the middle (8') section of the registration symbol. This element is omitted if no dots are present.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccordionLow(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accordion-low" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The accordion-low element indicates the presence of a dot in the low (16') section of the registration symbol. This element is omitted if no dot is present.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBassSeparator(XMLElement):
    
    TYPE = XSDComplexTypeStyleText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bass-separator" type="style-text" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The optional bass-separator element indicates that text, rather than a line or slash, separates the bass from what precedes it.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBassStep(XMLElement):
    
    TYPE = XSDComplexTypeBassStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bass-step" type="bass-step" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBassAlter(XMLElement):
    
    TYPE = XSDComplexTypeHarmonyAlter
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bass-alter" type="harmony-alter" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The bass-alter element represents the chromatic alteration of the bass of the current chord within the harmony element. In some chord styles, the text for the bass-step element may include bass-alter information. In that case, the print-object attribute of the bass-alter element can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the bass-step; it is right if not specified.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDegreeValue(XMLElement):
    
    TYPE = XSDComplexTypeDegreeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="degree-value" type="degree-value" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDegreeAlter(XMLElement):
    
    TYPE = XSDComplexTypeDegreeAlter
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="degree-alter" type="degree-alter" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDegreeType(XMLElement):
    
    TYPE = XSDComplexTypeDegreeType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="degree-type" type="degree-type" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDirectionType(XMLElement):
    
    TYPE = XSDComplexTypeDirectionType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="direction-type" type="direction-type" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOffset(XMLElement):
    
    TYPE = XSDComplexTypeOffset
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="offset" type="offset" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSound(XMLElement):
    
    TYPE = XSDComplexTypeSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sound" type="sound" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLListening(XMLElement):
    
    TYPE = XSDComplexTypeListening
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="listening" type="listening" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRehearsal(XMLElement):
    
    TYPE = XSDComplexTypeFormattedTextId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="rehearsal" type="formatted-text-id" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The rehearsal element specifies letters, numbers, and section names that are notated in the score for reference during rehearsal. The enclosure is square if not specified. The language is Italian ("it") if not specified. Left justification is used if not specified.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWords(XMLElement):
    
    TYPE = XSDComplexTypeFormattedTextId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="words" type="formatted-text-id">
    <xs:annotation>
        <xs:documentation>The words element specifies a standard text direction. The enclosure is none if not specified. The language is Italian ("it") if not specified. Left justification is used if not specified.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSymbol(XMLElement):
    
    TYPE = XSDComplexTypeFormattedSymbolId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="symbol" type="formatted-symbol-id">
    <xs:annotation>
        <xs:documentation>The symbol element specifies a musical symbol using a canonical SMuFL glyph name. It is used when an occasional musical symbol is interspersed into text. It should not be used in place of semantic markup, such as metronome marks that mix text and symbols. Left justification is used if not specified. Enclosure is none if not specified.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWedge(XMLElement):
    
    TYPE = XSDComplexTypeWedge
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="wedge" type="wedge" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDynamics(XMLElement):
    
    TYPE = XSDComplexTypeDynamics
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="dynamics" type="dynamics" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDashes(XMLElement):
    
    TYPE = XSDComplexTypeDashes
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="dashes" type="dashes" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBracket(XMLElement):
    
    TYPE = XSDComplexTypeBracket
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bracket" type="bracket" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPedal(XMLElement):
    
    TYPE = XSDComplexTypePedal
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pedal" type="pedal" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronome(XMLElement):
    
    TYPE = XSDComplexTypeMetronome
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome" type="metronome" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOctaveShift(XMLElement):
    
    TYPE = XSDComplexTypeOctaveShift
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="octave-shift" type="octave-shift" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHarpPedals(XMLElement):
    
    TYPE = XSDComplexTypeHarpPedals
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="harp-pedals" type="harp-pedals" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDamp(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="damp" type="empty-print-style-align-id">
    <xs:annotation>
        <xs:documentation>The damp element specifies a harp damping mark.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDampAll(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="damp-all" type="empty-print-style-align-id">
    <xs:annotation>
        <xs:documentation>The damp-all element specifies a harp damping mark for all strings.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEyeglasses(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPrintStyleAlignId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="eyeglasses" type="empty-print-style-align-id">
    <xs:annotation>
        <xs:documentation>The eyeglasses element represents the eyeglasses symbol, common in commercial music.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStringMute(XMLElement):
    
    TYPE = XSDComplexTypeStringMute
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="string-mute" type="string-mute" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLScordatura(XMLElement):
    
    TYPE = XSDComplexTypeScordatura
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="scordatura" type="scordatura" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLImage(XMLElement):
    
    TYPE = XSDComplexTypeImage
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="image" type="image" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPrincipalVoice(XMLElement):
    
    TYPE = XSDComplexTypePrincipalVoice
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="principal-voice" type="principal-voice" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPercussion(XMLElement):
    
    TYPE = XSDComplexTypePercussion
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="percussion" type="percussion" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccordionRegistration(XMLElement):
    
    TYPE = XSDComplexTypeAccordionRegistration
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accordion-registration" type="accordion-registration" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffDivide(XMLElement):
    
    TYPE = XSDComplexTypeStaffDivide
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-divide" type="staff-divide" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherDirection(XMLElement):
    
    TYPE = XSDComplexTypeOtherDirection
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-direction" type="other-direction" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFrameStrings(XMLElement):
    
    TYPE = XSDSimpleTypePositiveInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="frame-strings" type="xs:positiveInteger">
    <xs:annotation>
        <xs:documentation>The frame-strings element gives the overall size of the frame in vertical lines (strings).</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFrameFrets(XMLElement):
    
    TYPE = XSDSimpleTypePositiveInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="frame-frets" type="xs:positiveInteger">
    <xs:annotation>
        <xs:documentation>The frame-frets element gives the overall size of the frame in horizontal spaces (frets).</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFirstFret(XMLElement):
    
    TYPE = XSDComplexTypeFirstFret
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="first-fret" type="first-fret" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFrameNote(XMLElement):
    
    TYPE = XSDComplexTypeFrameNote
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="frame-note" type="frame-note" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLString(XMLElement):
    
    TYPE = XSDComplexTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="string" type="string" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFret(XMLElement):
    
    TYPE = XSDComplexTypeFret
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fret" type="fret" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFingering(XMLElement):
    
    TYPE = XSDComplexTypeFingering
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fingering" type="fingering" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBarre(XMLElement):
    
    TYPE = XSDComplexTypeBarre
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="barre" type="barre" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFeature(XMLElement):
    
    TYPE = XSDComplexTypeFeature
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="feature" type="feature" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFrame(XMLElement):
    
    TYPE = XSDComplexTypeFrame
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="frame" type="frame" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPedalTuning(XMLElement):
    
    TYPE = XSDComplexTypePedalTuning
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pedal-tuning" type="pedal-tuning" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSync(XMLElement):
    
    TYPE = XSDComplexTypeSync
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sync" type="sync" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherListening(XMLElement):
    
    TYPE = XSDComplexTypeOtherListening
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-listening" type="other-listening" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeatUnitTied(XMLElement):
    
    TYPE = XSDComplexTypeBeatUnitTied
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beat-unit-tied" type="beat-unit-tied" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPerMinute(XMLElement):
    
    TYPE = XSDComplexTypePerMinute
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="per-minute" type="per-minute" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeArrows(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-arrows" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>If the metronome-arrows element is present, it indicates that metric modulation arrows are displayed on both sides of the metronome mark.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeNote(XMLElement):
    
    TYPE = XSDComplexTypeMetronomeNote
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-note" type="metronome-note" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeRelation(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-relation" type="xs:string">
    <xs:annotation>
        <xs:documentation>The metronome-relation element describes the relationship symbol that goes between the two sets of metronome-note elements. The currently allowed value is equals, but this may expand in future versions. If the element is empty, the equals value is used.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeType(XMLElement):
    
    TYPE = XSDSimpleTypeNoteTypeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-type" type="note-type-value">
    <xs:annotation>
        <xs:documentation>The metronome-type element works like the type element in defining metric relationships.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeDot(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-dot" type="empty" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The metronome-dot element works like the dot element in defining metric relationships.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeBeam(XMLElement):
    
    TYPE = XSDComplexTypeMetronomeBeam
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-beam" type="metronome-beam" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeTied(XMLElement):
    
    TYPE = XSDComplexTypeMetronomeTied
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-tied" type="metronome-tied" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetronomeTuplet(XMLElement):
    
    TYPE = XSDComplexTypeMetronomeTuplet
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metronome-tuplet" type="metronome-tuplet" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeralRoot(XMLElement):
    
    TYPE = XSDComplexTypeNumeralRoot
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral-root" type="numeral-root" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeralAlter(XMLElement):
    
    TYPE = XSDComplexTypeHarmonyAlter
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral-alter" type="harmony-alter" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The numeral-alter element represents an alteration to the numeral-root, similar to the alter element for a pitch. The print-object attribute can be used to hide an alteration in cases such as when the MusicXML encoding of a 6 or 7 numeral-root in a minor key requires an alteration that is not displayed. The location attribute indicates whether the alteration should appear to the left or the right of the numeral-root. It is left by default.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeralKey(XMLElement):
    
    TYPE = XSDComplexTypeNumeralKey
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral-key" type="numeral-key" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeralFifths(XMLElement):
    
    TYPE = XSDSimpleTypeFifths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral-fifths" type="fifths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeralMode(XMLElement):
    
    TYPE = XSDSimpleTypeNumeralMode
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral-mode" type="numeral-mode" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPedalStep(XMLElement):
    
    TYPE = XSDSimpleTypeStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pedal-step" type="step">
    <xs:annotation>
        <xs:documentation>The pedal-step element defines the pitch step for a single harp pedal.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPedalAlter(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pedal-alter" type="semitones">
    <xs:annotation>
        <xs:documentation>The pedal-alter element defines the chromatic alteration for a single harp pedal.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGlass(XMLElement):
    
    TYPE = XSDComplexTypeGlass
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="glass" type="glass" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMetal(XMLElement):
    
    TYPE = XSDComplexTypeMetal
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="metal" type="metal" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWood(XMLElement):
    
    TYPE = XSDComplexTypeWood
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="wood" type="wood" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPitched(XMLElement):
    
    TYPE = XSDComplexTypePitched
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pitched" type="pitched" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMembrane(XMLElement):
    
    TYPE = XSDComplexTypeMembrane
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="membrane" type="membrane" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEffect(XMLElement):
    
    TYPE = XSDComplexTypeEffect
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="effect" type="effect" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTimpani(XMLElement):
    
    TYPE = XSDComplexTypeTimpani
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="timpani" type="timpani" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeater(XMLElement):
    
    TYPE = XSDComplexTypeBeater
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beater" type="beater" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStick(XMLElement):
    
    TYPE = XSDComplexTypeStick
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stick" type="stick" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStickLocation(XMLElement):
    
    TYPE = XSDSimpleTypeStickLocation
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stick-location" type="stick-location" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherPercussion(XMLElement):
    
    TYPE = XSDComplexTypeOtherText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-percussion" type="other-text">
    <xs:annotation>
        <xs:documentation>The other-percussion element represents percussion pictograms not defined elsewhere.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMeasureLayout(XMLElement):
    
    TYPE = XSDComplexTypeMeasureLayout
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="measure-layout" type="measure-layout" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMeasureNumbering(XMLElement):
    
    TYPE = XSDComplexTypeMeasureNumbering
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="measure-numbering" type="measure-numbering" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartNameDisplay(XMLElement):
    
    TYPE = XSDComplexTypeNameDisplay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-name-display" type="name-display" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartAbbreviationDisplay(XMLElement):
    
    TYPE = XSDComplexTypeNameDisplay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-abbreviation-display" type="name-display" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRootStep(XMLElement):
    
    TYPE = XSDComplexTypeRootStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="root-step" type="root-step" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRootAlter(XMLElement):
    
    TYPE = XSDComplexTypeHarmonyAlter
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="root-alter" type="harmony-alter" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The root-alter element represents the chromatic alteration of the root of the current chord within the harmony element. In some chord styles, the text for the root-step element may include root-alter information. In that case, the print-object attribute of the root-alter element can be set to no. The location attribute indicates whether the alteration should appear to the left or the right of the root-step; it is right by default.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccord(XMLElement):
    
    TYPE = XSDComplexTypeAccord
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accord" type="accord" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrumentChange(XMLElement):
    
    TYPE = XSDComplexTypeInstrumentChange
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument-change" type="instrument-change" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiDevice(XMLElement):
    
    TYPE = XSDComplexTypeMidiDevice
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-device" type="midi-device" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMidiInstrument(XMLElement):
    
    TYPE = XSDComplexTypeMidiInstrument
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="midi-instrument" type="midi-instrument" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPlay(XMLElement):
    
    TYPE = XSDComplexTypePlay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="play" type="play" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSwing(XMLElement):
    
    TYPE = XSDComplexTypeSwing
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="swing" type="swing" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStickType(XMLElement):
    
    TYPE = XSDSimpleTypeStickType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stick-type" type="stick-type" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStickMaterial(XMLElement):
    
    TYPE = XSDSimpleTypeStickMaterial
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stick-material" type="stick-material" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStraight(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="straight" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFirst(XMLElement):
    
    TYPE = XSDSimpleTypePositiveInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="first" type="xs:positiveInteger" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSecond(XMLElement):
    
    TYPE = XSDSimpleTypePositiveInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="second" type="xs:positiveInteger" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSwingType(XMLElement):
    
    TYPE = XSDSimpleTypeSwingTypeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="swing-type" type="swing-type-value" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSwingStyle(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="swing-style" type="xs:string" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEncodingDate(XMLElement):
    
    TYPE = XSDSimpleTypeYyyyMmDd
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="encoding-date" type="yyyy-mm-dd" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEncoder(XMLElement):
    
    TYPE = XSDComplexTypeTypedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="encoder" type="typed-text" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSoftware(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="software" type="xs:string" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEncodingDescription(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="encoding-description" type="xs:string" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSupports(XMLElement):
    
    TYPE = XSDComplexTypeSupports
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="supports" type="supports" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCreator(XMLElement):
    
    TYPE = XSDComplexTypeTypedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="creator" type="typed-text" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The creator element is borrowed from Dublin Core. It is used for the creators of the score. The type attribute is used to distinguish different creative contributions. Thus, there can be multiple creators within an identification. Standard type values are composer, lyricist, and arranger. Other type values may be used for different types of creative roles. The type attribute should usually be used even if there is just a single creator element. The MusicXML format does not use the creator / contributor distinction from Dublin Core.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRights(XMLElement):
    
    TYPE = XSDComplexTypeTypedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="rights" type="typed-text" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The rights element is borrowed from Dublin Core. It contains copyright and other intellectual property notices. Words, music, and derivatives can have different types, so multiple rights elements with different type attributes are supported. Standard type values are music, words, and arrangement, but other types may be used. The type attribute is only needed when there are multiple rights elements.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEncoding(XMLElement):
    
    TYPE = XSDComplexTypeEncoding
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="encoding" type="encoding" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSource(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="source" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The source for the music that is encoded. This is similar to the Dublin Core source element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRelation(XMLElement):
    
    TYPE = XSDComplexTypeTypedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="relation" type="typed-text" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>A related resource for the music that is encoded. This is similar to the Dublin Core relation element. Standard type values are music, words, and arrangement, but other types may be used.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMiscellaneous(XMLElement):
    
    TYPE = XSDComplexTypeMiscellaneous
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="miscellaneous" type="miscellaneous" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMiscellaneousField(XMLElement):
    
    TYPE = XSDComplexTypeMiscellaneousField
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="miscellaneous-field" type="miscellaneous-field" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLineWidth(XMLElement):
    
    TYPE = XSDComplexTypeLineWidth
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="line-width" type="line-width" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNoteSize(XMLElement):
    
    TYPE = XSDComplexTypeNoteSize
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="note-size" type="note-size" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDistance(XMLElement):
    
    TYPE = XSDComplexTypeDistance
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="distance" type="distance" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGlyph(XMLElement):
    
    TYPE = XSDComplexTypeGlyph
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="glyph" type="glyph" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherAppearance(XMLElement):
    
    TYPE = XSDComplexTypeOtherAppearance
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-appearance" type="other-appearance" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMeasureDistance(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="measure-distance" type="tenths" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The measure-distance element specifies the horizontal distance from the previous measure. This value is only used for systems where there is horizontal whitespace in the middle of a system, as in systems with codas. To specify the measure width, use the width attribute of the measure element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPageHeight(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="page-height" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPageWidth(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="page-width" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPageMargins(XMLElement):
    
    TYPE = XSDComplexTypePageMargins
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="page-margins" type="page-margins" minOccurs="0" maxOccurs="2" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMillimeters(XMLElement):
    
    TYPE = XSDSimpleTypeMillimeters
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="millimeters" type="millimeters" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTenths(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tenths" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffDistance(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-distance" type="tenths" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLeftDivider(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPrintObjectStyleAlign
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="left-divider" type="empty-print-object-style-align" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRightDivider(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPrintObjectStyleAlign
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="right-divider" type="empty-print-object-style-align" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSystemMargins(XMLElement):
    
    TYPE = XSDComplexTypeSystemMargins
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="system-margins" type="system-margins" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSystemDistance(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="system-distance" type="tenths" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTopSystemDistance(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="top-system-distance" type="tenths" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSystemDividers(XMLElement):
    
    TYPE = XSDComplexTypeSystemDividers
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="system-dividers" type="system-dividers" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccent(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accent" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The accent element indicates a regular horizontal accent mark.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStrongAccent(XMLElement):
    
    TYPE = XSDComplexTypeStrongAccent
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="strong-accent" type="strong-accent">
    <xs:annotation>
        <xs:documentation>The strong-accent element indicates a vertical accent mark.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaccato(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staccato" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The staccato element is used for a dot articulation, as opposed to a stroke or a wedge.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTenuto(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tenuto" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The tenuto element indicates a tenuto line symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDetachedLegato(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="detached-legato" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The detached-legato element indicates the combination of a tenuto line and staccato dot symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaccatissimo(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staccatissimo" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The staccatissimo element is used for a wedge articulation, as opposed to a dot or a stroke.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSpiccato(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="spiccato" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The spiccato element is used for a stroke articulation, as opposed to a dot or a wedge.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLScoop(XMLElement):
    
    TYPE = XSDComplexTypeEmptyLine
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="scoop" type="empty-line">
    <xs:annotation>
        <xs:documentation>The scoop element is an indeterminate slide attached to a single note. The scoop appears before the main note and comes from below the main pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPlop(XMLElement):
    
    TYPE = XSDComplexTypeEmptyLine
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="plop" type="empty-line">
    <xs:annotation>
        <xs:documentation>The plop element is an indeterminate slide attached to a single note. The plop appears before the main note and comes from above the main pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDoit(XMLElement):
    
    TYPE = XSDComplexTypeEmptyLine
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="doit" type="empty-line">
    <xs:annotation>
        <xs:documentation>The doit element is an indeterminate slide attached to a single note. The doit appears after the main note and goes above the main pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFalloff(XMLElement):
    
    TYPE = XSDComplexTypeEmptyLine
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="falloff" type="empty-line">
    <xs:annotation>
        <xs:documentation>The falloff element is an indeterminate slide attached to a single note. The falloff appears after the main note and goes below the main pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBreathMark(XMLElement):
    
    TYPE = XSDComplexTypeBreathMark
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="breath-mark" type="breath-mark" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCaesura(XMLElement):
    
    TYPE = XSDComplexTypeCaesura
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="caesura" type="caesura" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStress(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stress" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The stress element indicates a stressed note.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLUnstress(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="unstress" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The unstress element indicates an unstressed note. It is often notated using a u-shaped symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSoftAccent(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="soft-accent" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The soft-accent element indicates a soft accent that is not as heavy as a normal accent. It is often notated as &lt;&gt;. It can be combined with other articulations to implement the first eight symbols in the SMuFL Articulation supplement range.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherArticulation(XMLElement):
    
    TYPE = XSDComplexTypeOtherPlacementText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-articulation" type="other-placement-text">
    <xs:annotation>
        <xs:documentation>The other-articulation element is used to define any articulations not yet in the MusicXML format. The smufl attribute can be used to specify a particular articulation, allowing application interoperability without requiring every SMuFL articulation to have a MusicXML element equivalent. Using the other-articulation element without the smufl attribute allows for extended representation, though without application interoperability.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArrowDirection(XMLElement):
    
    TYPE = XSDSimpleTypeArrowDirection
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="arrow-direction" type="arrow-direction" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArrowStyle(XMLElement):
    
    TYPE = XSDSimpleTypeArrowStyle
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="arrow-style" type="arrow-style" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArrowhead(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="arrowhead" type="empty" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCircularArrow(XMLElement):
    
    TYPE = XSDSimpleTypeCircularArrow
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="circular-arrow" type="circular-arrow" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBendAlter(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bend-alter" type="semitones">
    <xs:annotation>
        <xs:documentation>The bend-alter element indicates the number of semitones in the bend, similar to the alter element. As with the alter element, numbers like 0.5 can be used to indicate microtones. Negative values indicate pre-bends or releases. The pre-bend and release elements are used to distinguish what is intended. Because the bend-alter element represents the number of steps in the bend, a release after a bend has a negative bend-alter value, not a zero value.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPreBend(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pre-bend" type="empty">
    <xs:annotation>
        <xs:documentation>The pre-bend element indicates that a bend is a pre-bend rather than a normal bend or a release.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRelease(XMLElement):
    
    TYPE = XSDComplexTypeRelease
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="release" type="release" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWithBar(XMLElement):
    
    TYPE = XSDComplexTypePlacementText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="with-bar" type="placement-text" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The with-bar element indicates that the bend is to be done at the bridge with a whammy or vibrato bar. The content of the element indicates how this should be notated. Content values of "scoop" and "dip" refer to the SMuFL guitarVibratoBarScoop and guitarVibratoBarDip glyphs.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPrefix(XMLElement):
    
    TYPE = XSDComplexTypeStyleText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="prefix" type="style-text" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Values for the prefix element include plus and the accidental values sharp, flat, natural, double-sharp, flat-flat, and sharp-sharp. The prefix element may contain additional values for symbols specific to particular figured bass styles.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFigureNumber(XMLElement):
    
    TYPE = XSDComplexTypeStyleText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="figure-number" type="style-text" minOccurs="0">
    <xs:annotation>
        <xs:documentation>A figure-number is a number. Overstrikes of the figure number are represented in the suffix element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSuffix(XMLElement):
    
    TYPE = XSDComplexTypeStyleText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="suffix" type="style-text" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Values for the suffix element include plus and the accidental values sharp, flat, natural, double-sharp, flat-flat, and sharp-sharp. Suffixes include both symbols that come after the figure number and those that overstrike the figure number. The suffix values slash, back-slash, and vertical are used for slashed numbers indicating chromatic alteration. The orientation and display of the slash usually depends on the figure number. The suffix element may contain additional values for symbols specific to particular figured bass styles.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLExtend(XMLElement):
    
    TYPE = XSDComplexTypeExtend
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="extend" type="extend" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFigure(XMLElement):
    
    TYPE = XSDComplexTypeFigure
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="figure" type="figure" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHarmonClosed(XMLElement):
    
    TYPE = XSDComplexTypeHarmonClosed
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="harmon-closed" type="harmon-closed" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNatural(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="natural" type="empty">
    <xs:annotation>
        <xs:documentation>The natural element indicates that this is a natural harmonic. These are usually notated at base pitch rather than sounding pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArtificial(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="artificial" type="empty">
    <xs:annotation>
        <xs:documentation>The artificial element indicates that this is an artificial harmonic.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBasePitch(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="base-pitch" type="empty">
    <xs:annotation>
        <xs:documentation>The base pitch is the pitch at which the string is played before touching to create the harmonic.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTouchingPitch(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="touching-pitch" type="empty">
    <xs:annotation>
        <xs:documentation>The touching-pitch is the pitch at which the string is touched lightly to produce the harmonic.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSoundingPitch(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sounding-pitch" type="empty">
    <xs:annotation>
        <xs:documentation>The sounding-pitch is the pitch which is heard when playing the harmonic.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHoleType(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="hole-type" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The content of the optional hole-type element indicates what the hole symbol represents in terms of instrument fingering or other techniques.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHoleClosed(XMLElement):
    
    TYPE = XSDComplexTypeHoleClosed
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="hole-closed" type="hole-closed" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHoleShape(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="hole-shape" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The optional hole-shape element indicates the shape of the hole symbol; the default is a circle.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAssess(XMLElement):
    
    TYPE = XSDComplexTypeAssess
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="assess" type="assess" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWait(XMLElement):
    
    TYPE = XSDComplexTypeWait
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="wait" type="wait" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherListen(XMLElement):
    
    TYPE = XSDComplexTypeOtherListening
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-listen" type="other-listening" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSyllabic(XMLElement):
    
    TYPE = XSDSimpleTypeSyllabic
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="syllabic" type="syllabic" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLText(XMLElement):
    
    TYPE = XSDComplexTypeTextElementData
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="text" type="text-element-data" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLElision(XMLElement):
    
    TYPE = XSDComplexTypeElision
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="elision" type="elision" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLaughing(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="laughing" type="empty">
    <xs:annotation>
        <xs:documentation>The laughing element represents a laughing voice.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHumming(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="humming" type="empty">
    <xs:annotation>
        <xs:documentation>The humming element represents a humming voice.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEndLine(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="end-line" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The end-line element comes from RP-017 for Standard MIDI File Lyric meta-events. It facilitates lyric display for Karaoke and similar applications.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEndParagraph(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="end-paragraph" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The end-paragraph element comes from RP-017 for Standard MIDI File Lyric meta-events. It facilitates lyric display for Karaoke and similar applications.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTied(XMLElement):
    
    TYPE = XSDComplexTypeTied
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tied" type="tied" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSlur(XMLElement):
    
    TYPE = XSDComplexTypeSlur
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="slur" type="slur" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTuplet(XMLElement):
    
    TYPE = XSDComplexTypeTuplet
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet" type="tuplet" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGlissando(XMLElement):
    
    TYPE = XSDComplexTypeGlissando
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="glissando" type="glissando" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSlide(XMLElement):
    
    TYPE = XSDComplexTypeSlide
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="slide" type="slide" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOrnaments(XMLElement):
    
    TYPE = XSDComplexTypeOrnaments
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ornaments" type="ornaments" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTechnical(XMLElement):
    
    TYPE = XSDComplexTypeTechnical
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="technical" type="technical" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArticulations(XMLElement):
    
    TYPE = XSDComplexTypeArticulations
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="articulations" type="articulations" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArpeggiate(XMLElement):
    
    TYPE = XSDComplexTypeArpeggiate
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="arpeggiate" type="arpeggiate" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNonArpeggiate(XMLElement):
    
    TYPE = XSDComplexTypeNonArpeggiate
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="non-arpeggiate" type="non-arpeggiate" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccidentalMark(XMLElement):
    
    TYPE = XSDComplexTypeAccidentalMark
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accidental-mark" type="accidental-mark" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherNotation(XMLElement):
    
    TYPE = XSDComplexTypeOtherNotation
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-notation" type="other-notation" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGrace(XMLElement):
    
    TYPE = XSDComplexTypeGrace
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="grace" type="grace" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTie(XMLElement):
    
    TYPE = XSDComplexTypeTie
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tie" type="tie" minOccurs="0" maxOccurs="2" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCue(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="cue" type="empty" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrument(XMLElement):
    
    TYPE = XSDComplexTypeInstrument
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument" type="instrument" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLType(XMLElement):
    
    TYPE = XSDComplexTypeNoteType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="type" type="note-type" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDot(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="dot" type="empty-placement" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>One dot element is used for each dot of prolongation. The placement attribute is used to specify whether the dot should appear above or below the staff line. It is ignored for notes that appear on a staff space.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAccidental(XMLElement):
    
    TYPE = XSDComplexTypeAccidental
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="accidental" type="accidental" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTimeModification(XMLElement):
    
    TYPE = XSDComplexTypeTimeModification
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="time-modification" type="time-modification" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStem(XMLElement):
    
    TYPE = XSDComplexTypeStem
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stem" type="stem" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNotehead(XMLElement):
    
    TYPE = XSDComplexTypeNotehead
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="notehead" type="notehead" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNoteheadText(XMLElement):
    
    TYPE = XSDComplexTypeNoteheadText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="notehead-text" type="notehead-text" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeam(XMLElement):
    
    TYPE = XSDComplexTypeBeam
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beam" type="beam" minOccurs="0" maxOccurs="8" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNotations(XMLElement):
    
    TYPE = XSDComplexTypeNotations
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="notations" type="notations" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLyric(XMLElement):
    
    TYPE = XSDComplexTypeLyric
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="lyric" type="lyric" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLListen(XMLElement):
    
    TYPE = XSDComplexTypeListen
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="listen" type="listen" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTrillMark(XMLElement):
    
    TYPE = XSDComplexTypeEmptyTrillSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="trill-mark" type="empty-trill-sound">
    <xs:annotation>
        <xs:documentation>The trill-mark element represents the trill-mark symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTurn(XMLElement):
    
    TYPE = XSDComplexTypeHorizontalTurn
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="turn" type="horizontal-turn">
    <xs:annotation>
        <xs:documentation>The turn element is the normal turn shape which goes up then down.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDelayedTurn(XMLElement):
    
    TYPE = XSDComplexTypeHorizontalTurn
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="delayed-turn" type="horizontal-turn">
    <xs:annotation>
        <xs:documentation>The delayed-turn element indicates a normal turn that is delayed until the end of the current note.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInvertedTurn(XMLElement):
    
    TYPE = XSDComplexTypeHorizontalTurn
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="inverted-turn" type="horizontal-turn">
    <xs:annotation>
        <xs:documentation>The inverted-turn element has the shape which goes down and then up.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDelayedInvertedTurn(XMLElement):
    
    TYPE = XSDComplexTypeHorizontalTurn
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="delayed-inverted-turn" type="horizontal-turn">
    <xs:annotation>
        <xs:documentation>The delayed-inverted-turn element indicates an inverted turn that is delayed until the end of the current note.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVerticalTurn(XMLElement):
    
    TYPE = XSDComplexTypeEmptyTrillSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="vertical-turn" type="empty-trill-sound">
    <xs:annotation>
        <xs:documentation>The vertical-turn element has the turn symbol shape arranged vertically going from upper left to lower right.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInvertedVerticalTurn(XMLElement):
    
    TYPE = XSDComplexTypeEmptyTrillSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="inverted-vertical-turn" type="empty-trill-sound">
    <xs:annotation>
        <xs:documentation>The inverted-vertical-turn element has the turn symbol shape arranged vertically going from upper right to lower left.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLShake(XMLElement):
    
    TYPE = XSDComplexTypeEmptyTrillSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="shake" type="empty-trill-sound">
    <xs:annotation>
        <xs:documentation>The shake element has a similar appearance to an inverted-mordent element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMordent(XMLElement):
    
    TYPE = XSDComplexTypeMordent
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="mordent" type="mordent">
    <xs:annotation>
        <xs:documentation>The mordent element represents the sign with the vertical line. The choice of which mordent sign is inverted differs between MusicXML and SMuFL. The long attribute is "no" by default.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInvertedMordent(XMLElement):
    
    TYPE = XSDComplexTypeMordent
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="inverted-mordent" type="mordent">
    <xs:annotation>
        <xs:documentation>The inverted-mordent element represents the sign without the vertical line. The choice of which mordent is inverted differs between MusicXML and SMuFL. The long attribute is "no" by default.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSchleifer(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="schleifer" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The name for this ornament is based on the German, to avoid confusion with the more common slide element defined earlier.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTremolo(XMLElement):
    
    TYPE = XSDComplexTypeTremolo
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tremolo" type="tremolo" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHaydn(XMLElement):
    
    TYPE = XSDComplexTypeEmptyTrillSound
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="haydn" type="empty-trill-sound">
    <xs:annotation>
        <xs:documentation>The haydn element represents the Haydn ornament. This is defined in SMuFL as ornamentHaydn.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherOrnament(XMLElement):
    
    TYPE = XSDComplexTypeOtherPlacementText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-ornament" type="other-placement-text">
    <xs:annotation>
        <xs:documentation>The other-ornament element is used to define any ornaments not yet in the MusicXML format. The smufl attribute can be used to specify a particular ornament, allowing application interoperability without requiring every SMuFL ornament to have a MusicXML element equivalent. Using the other-ornament element without the smufl attribute allows for extended representation, though without application interoperability.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStep(XMLElement):
    
    TYPE = XSDSimpleTypeStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="step" type="step" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAlter(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="alter" type="semitones" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOctave(XMLElement):
    
    TYPE = XSDSimpleTypeOctave
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="octave" type="octave" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLUpBow(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="up-bow" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The up-bow element represents the symbol that is used both for up-bowing on bowed instruments, and up-stroke on plucked instruments.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDownBow(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="down-bow" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The down-bow element represents the symbol that is used both for down-bowing on bowed instruments, and down-stroke on plucked instruments.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHarmonic(XMLElement):
    
    TYPE = XSDComplexTypeHarmonic
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="harmonic" type="harmonic" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOpenString(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="open-string" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The open-string element represents the zero-shaped open string symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLThumbPosition(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="thumb-position" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The thumb-position element represents the thumb position symbol. This is a circle with a line, where the line does not come within the circle. It is distinct from the snap pizzicato symbol, where the line comes inside the circle.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPluck(XMLElement):
    
    TYPE = XSDComplexTypePlacementText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pluck" type="placement-text">
    <xs:annotation>
        <xs:documentation>The pluck element is used to specify the plucking fingering on a fretted instrument, where the fingering element refers to the fretting fingering. Typical values are p, i, m, a for pulgar/thumb, indicio/index, medio/middle, and anular/ring fingers.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDoubleTongue(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="double-tongue" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The double-tongue element represents the double tongue symbol (two dots arranged horizontally).</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTripleTongue(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="triple-tongue" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The triple-tongue element represents the triple tongue symbol (three dots arranged horizontally).</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStopped(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="stopped" type="empty-placement-smufl">
    <xs:annotation>
        <xs:documentation>The stopped element represents the stopped symbol, which looks like a plus sign. The smufl attribute distinguishes different SMuFL glyphs that have a similar appearance such as handbellsMalletBellSuspended and guitarClosePedal. If not present, the default glyph is brassMuteClosed.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSnapPizzicato(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="snap-pizzicato" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The snap-pizzicato element represents the snap pizzicato symbol. This is a circle with a line, where the line comes inside the circle. It is distinct from the thumb-position symbol, where the line does not come inside the circle.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHammerOn(XMLElement):
    
    TYPE = XSDComplexTypeHammerOnPullOff
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="hammer-on" type="hammer-on-pull-off" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPullOff(XMLElement):
    
    TYPE = XSDComplexTypeHammerOnPullOff
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pull-off" type="hammer-on-pull-off" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBend(XMLElement):
    
    TYPE = XSDComplexTypeBend
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bend" type="bend" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTap(XMLElement):
    
    TYPE = XSDComplexTypeTap
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tap" type="tap" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHeel(XMLElement):
    
    TYPE = XSDComplexTypeHeelToe
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="heel" type="heel-toe" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLToe(XMLElement):
    
    TYPE = XSDComplexTypeHeelToe
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="toe" type="heel-toe" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFingernails(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fingernails" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The fingernails element is used in notation for harp and other plucked string instruments.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHole(XMLElement):
    
    TYPE = XSDComplexTypeHole
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="hole" type="hole" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLArrow(XMLElement):
    
    TYPE = XSDComplexTypeArrow
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="arrow" type="arrow" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHandbell(XMLElement):
    
    TYPE = XSDComplexTypeHandbell
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="handbell" type="handbell" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBrassBend(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="brass-bend" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The brass-bend element represents the u-shaped bend symbol used in brass notation, distinct from the bend element used in guitar music.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFlip(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="flip" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The flip element represents the flip symbol used in brass notation.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSmear(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="smear" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The smear element represents the tilde-shaped smear symbol used in brass notation.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOpen(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="open" type="empty-placement-smufl">
    <xs:annotation>
        <xs:documentation>The open element represents the open symbol, which looks like a circle. The smufl attribute can be used to distinguish different SMuFL glyphs that have a similar appearance such as brassMuteOpen and guitarOpenPedal. If not present, the default glyph is brassMuteOpen.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHalfMuted(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacementSmufl
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="half-muted" type="empty-placement-smufl">
    <xs:annotation>
        <xs:documentation>The half-muted element represents the half-muted symbol, which looks like a circle with a plus sign inside. The smufl attribute can be used to distinguish different SMuFL glyphs that have a similar appearance such as brassMuteHalfClosed and guitarHalfOpenPedal. If not present, the default glyph is brassMuteHalfClosed.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHarmonMute(XMLElement):
    
    TYPE = XSDComplexTypeHarmonMute
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="harmon-mute" type="harmon-mute" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGolpe(XMLElement):
    
    TYPE = XSDComplexTypeEmptyPlacement
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="golpe" type="empty-placement">
    <xs:annotation>
        <xs:documentation>The golpe element represents the golpe symbol that is used for tapping the pick guard in guitar music.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOtherTechnical(XMLElement):
    
    TYPE = XSDComplexTypeOtherPlacementText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="other-technical" type="other-placement-text">
    <xs:annotation>
        <xs:documentation>The other-technical element is used to define any technical indications not yet in the MusicXML format. The smufl attribute can be used to specify a particular glyph, allowing application interoperability without requiring every SMuFL technical indication to have a MusicXML element equivalent. Using the other-technical element without the smufl attribute allows for extended representation, though without application interoperability.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLActualNotes(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="actual-notes" type="xs:nonNegativeInteger">
    <xs:annotation>
        <xs:documentation>The actual-notes element describes how many notes are played in the time usually occupied by the number in the normal-notes element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNormalNotes(XMLElement):
    
    TYPE = XSDSimpleTypeNonNegativeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="normal-notes" type="xs:nonNegativeInteger">
    <xs:annotation>
        <xs:documentation>The normal-notes element describes how many notes are usually played in the time occupied by the number in the actual-notes element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNormalType(XMLElement):
    
    TYPE = XSDSimpleTypeNoteTypeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="normal-type" type="note-type-value">
    <xs:annotation>
        <xs:documentation>If the type associated with the number in the normal-notes element is different than the current note type (e.g., a quarter note within an eighth note triplet), then the normal-notes type (e.g. eighth) is specified in the normal-type and normal-dot elements.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNormalDot(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="normal-dot" type="empty" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The normal-dot element is used to specify dotted normal tuplet types.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTupletActual(XMLElement):
    
    TYPE = XSDComplexTypeTupletPortion
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet-actual" type="tuplet-portion" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The tuplet-actual element provide optional full control over how the actual part of the tuplet is displayed, including number and note type (with dots). If any of these elements are absent, their values are based on the time-modification element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTupletNormal(XMLElement):
    
    TYPE = XSDComplexTypeTupletPortion
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet-normal" type="tuplet-portion" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The tuplet-normal element provide optional full control over how the normal part of the tuplet is displayed, including number and note type (with dots). If any of these elements are absent, their values are based on the time-modification element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTupletNumber(XMLElement):
    
    TYPE = XSDComplexTypeTupletNumber
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet-number" type="tuplet-number" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTupletType(XMLElement):
    
    TYPE = XSDComplexTypeTupletType
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet-type" type="tuplet-type" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTupletDot(XMLElement):
    
    TYPE = XSDComplexTypeTupletDot
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuplet-dot" type="tuplet-dot" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCreditType(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="credit-type" type="xs:string" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLink(XMLElement):
    
    TYPE = XSDComplexTypeLink
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="link" type="link" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBookmark(XMLElement):
    
    TYPE = XSDComplexTypeBookmark
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bookmark" type="bookmark" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCreditImage(XMLElement):
    
    TYPE = XSDComplexTypeImage
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="credit-image" type="image" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCreditWords(XMLElement):
    
    TYPE = XSDComplexTypeFormattedTextId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="credit-words" type="formatted-text-id" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCreditSymbol(XMLElement):
    
    TYPE = XSDComplexTypeFormattedSymbolId
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="credit-symbol" type="formatted-symbol-id" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLScaling(XMLElement):
    
    TYPE = XSDComplexTypeScaling
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="scaling" type="scaling" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLConcertScore(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="concert-score" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The presence of a concert-score element indicates that a score is displayed in concert pitch. It is used for scores that contain parts for transposing instruments.

A document with a concert-score element may not contain any transpose elements that have non-zero values for either the diatonic or chromatic elements. Concert scores may include octave transpositions, so transpose elements with a double element or a non-zero octave-change element value are permitted.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAppearance(XMLElement):
    
    TYPE = XSDComplexTypeAppearance
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="appearance" type="appearance" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMusicFont(XMLElement):
    
    TYPE = XSDComplexTypeEmptyFont
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="music-font" type="empty-font" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWordFont(XMLElement):
    
    TYPE = XSDComplexTypeEmptyFont
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="word-font" type="empty-font" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLyricFont(XMLElement):
    
    TYPE = XSDComplexTypeLyricFont
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="lyric-font" type="lyric-font" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLyricLanguage(XMLElement):
    
    TYPE = XSDComplexTypeLyricLanguage
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="lyric-language" type="lyric-language" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupName(XMLElement):
    
    TYPE = XSDComplexTypeGroupName
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-name" type="group-name" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupNameDisplay(XMLElement):
    
    TYPE = XSDComplexTypeNameDisplay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-name-display" type="name-display" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Formatting specified in the group-name-display element overrides formatting specified in the group-name element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupAbbreviation(XMLElement):
    
    TYPE = XSDComplexTypeGroupName
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-abbreviation" type="group-name" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupAbbreviationDisplay(XMLElement):
    
    TYPE = XSDComplexTypeNameDisplay
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-abbreviation-display" type="name-display" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Formatting specified in the group-abbreviation-display element overrides formatting specified in the group-abbreviation element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupSymbol(XMLElement):
    
    TYPE = XSDComplexTypeGroupSymbol
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-symbol" type="group-symbol" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupBarline(XMLElement):
    
    TYPE = XSDComplexTypeGroupBarline
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-barline" type="group-barline" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupTime(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-time" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The group-time element indicates that the displayed time signatures should stretch across all parts and staves in the group.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrumentLink(XMLElement):
    
    TYPE = XSDComplexTypeInstrumentLink
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument-link" type="instrument-link" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroupLink(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group-link" type="xs:string" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>Multiple part-link elements can reference different types of linked documents, such as parts and condensed score. The optional group-link elements identify the groups used in the linked document. The content of a group-link element should match the content of a group element in the linked document.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPlayerName(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="player-name" type="xs:string">
    <xs:annotation>
        <xs:documentation>The player-name element is typically used within a software application, rather than appearing on the printed page of a score.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrumentName(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument-name" type="xs:string">
    <xs:annotation>
        <xs:documentation>The instrument-name element is typically used within a software application, rather than appearing on the printed page of a score.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrumentAbbreviation(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument-abbreviation" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The optional instrument-abbreviation element is typically used within a software application, rather than appearing on the printed page of a score.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLIdentification(XMLElement):
    
    TYPE = XSDComplexTypeIdentification
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="identification" type="identification" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartLink(XMLElement):
    
    TYPE = XSDComplexTypePartLink
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-link" type="part-link" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartName(XMLElement):
    
    TYPE = XSDComplexTypePartName
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-name" type="part-name" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartAbbreviation(XMLElement):
    
    TYPE = XSDComplexTypePartName
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-abbreviation" type="part-name" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGroup(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="group" type="xs:string" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The group element allows the use of different versions of the part for different purposes. Typical values include score, parts, sound, and data. Ordering information can be derived from the ordering within a MusicXML score or opus.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLScoreInstrument(XMLElement):
    
    TYPE = XSDComplexTypeScoreInstrument
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="score-instrument" type="score-instrument" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPlayer(XMLElement):
    
    TYPE = XSDComplexTypePlayer
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="player" type="player" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVirtualLibrary(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="virtual-library" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The virtual-library element indicates the virtual instrument library name.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVirtualName(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="virtual-name" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The virtual-name element indicates the library-specific name for the virtual instrument.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWorkNumber(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="work-number" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The work-number element specifies the number of a work, such as its opus number.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWorkTitle(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="work-title" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The work-title element specifies the title of a work, not including its opus or other work number.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOpus(XMLElement):
    
    TYPE = XSDComplexTypeOpus
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="opus" type="opus" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFootnote(XMLElement):
    
    TYPE = XSDComplexTypeFormattedText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="footnote" type="formatted-text" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLevel(XMLElement):
    
    TYPE = XSDComplexTypeLevel
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="level" type="level" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaff(XMLElement):
    
    TYPE = XSDSimpleTypePositiveInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff" type="xs:positiveInteger">
    <xs:annotation>
        <xs:documentation>Staff assignment is only needed for music notated on multiple staves. Used by both notes and directions. Staff values are numbers, with 1 referring to the top-most staff in a part.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTuningStep(XMLElement):
    
    TYPE = XSDSimpleTypeStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuning-step" type="step">
    <xs:annotation>
        <xs:documentation>The tuning-step element is represented like the step element, with a different name to reflect its different function in string tuning.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTuningAlter(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuning-alter" type="semitones" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The tuning-alter element is represented like the alter element, with a different name to reflect its different function in string tuning.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTuningOctave(XMLElement):
    
    TYPE = XSDSimpleTypeOctave
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="tuning-octave" type="octave">
    <xs:annotation>
        <xs:documentation>The tuning-octave element is represented like the octave element, with a different name to reflect its different function in string tuning.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInstrumentSound(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="instrument-sound" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The instrument-sound element describes the default timbre of the score-instrument. This description is independent of a particular virtual or MIDI instrument specification and allows playback to be shared more easily between applications and libraries.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSolo(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="solo" type="empty">
    <xs:annotation>
        <xs:documentation>The solo element is present if performance is intended by a solo instrument.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLEnsemble(XMLElement):
    
    TYPE = XSDSimpleTypePositiveIntegerOrEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="ensemble" type="positive-integer-or-empty">
    <xs:annotation>
        <xs:documentation>The ensemble element is present if performance is intended by an ensemble such as an orchestral section. The text of the ensemble element contains the size of the section, or is empty if the ensemble size is not specified.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVirtualInstrument(XMLElement):
    
    TYPE = XSDComplexTypeVirtualInstrument
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="virtual-instrument" type="virtual-instrument" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLVoice(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="voice" type="xs:string" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSign(XMLElement):
    
    TYPE = XSDSimpleTypeClefSign
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="sign" type="clef-sign">
    <xs:annotation>
        <xs:documentation>The sign element represents the clef symbol.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLine(XMLElement):
    
    TYPE = XSDSimpleTypeStaffLinePosition
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="line" type="staff-line-position" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Line numbers are counted from the bottom of the staff. They are only needed with the G, F, and C signs in order to position a pitch correctly on the staff. Standard values are 2 for the G sign (treble clef), 4 for the F sign (bass clef), and 3 for the C sign (alto clef). Line values can be used to specify positions outside the staff, such as a C clef positioned in the middle of a grand staff.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLClefOctaveChange(XMLElement):
    
    TYPE = XSDSimpleTypeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="clef-octave-change" type="xs:integer" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The clef-octave-change element is used for transposing clefs. A treble clef for tenors would have a value of -1.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKeyStep(XMLElement):
    
    TYPE = XSDSimpleTypeStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="key-step" type="step">
    <xs:annotation>
        <xs:documentation>Non-traditional key signatures are represented using a list of altered tones. The key-step element indicates the pitch step to be altered, represented using the same names as in the step element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKeyAlter(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="key-alter" type="semitones">
    <xs:annotation>
        <xs:documentation>Non-traditional key signatures are represented using a list of altered tones. The key-alter element represents the alteration for a given pitch step, represented with semitones in the same manner as the alter element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKeyAccidental(XMLElement):
    
    TYPE = XSDComplexTypeKeyAccidental
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="key-accidental" type="key-accidental" minOccurs="0">
    <xs:annotation>
        <xs:documentation>Non-traditional key signatures are represented using a list of altered tones. The key-accidental element indicates the accidental to be displayed in the key signature, represented in the same manner as the accidental element. It is used for disambiguating microtonal accidentals.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSlashType(XMLElement):
    
    TYPE = XSDSimpleTypeNoteTypeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="slash-type" type="note-type-value">
    <xs:annotation>
        <xs:documentation>The slash-type element indicates the graphical note type to use for the display of repetition marks.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSlashDot(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="slash-dot" type="empty" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The slash-dot element is used to specify any augmentation dots in the note type used to display repetition marks.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLExceptVoice(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="except-voice" type="xs:string" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The except-voice element is used to specify a combination of slash notation and regular notation. Any note elements that are in voices specified by the except-voice elements are displayed in normal notation, in addition to the slash notation that is always displayed.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeats(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beats" type="xs:string">
    <xs:annotation>
        <xs:documentation>The beats element indicates the number of beats, as found in the numerator of a time signature.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeatType(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beat-type" type="xs:string">
    <xs:annotation>
        <xs:documentation>The beat-type element indicates the beat unit, as found in the denominator of a time signature.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCancel(XMLElement):
    
    TYPE = XSDComplexTypeCancel
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="cancel" type="cancel" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFifths(XMLElement):
    
    TYPE = XSDSimpleTypeFifths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="fifths" type="fifths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMode(XMLElement):
    
    TYPE = XSDSimpleTypeMode
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="mode" type="mode" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDiatonic(XMLElement):
    
    TYPE = XSDSimpleTypeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="diatonic" type="xs:integer" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The diatonic element specifies the number of pitch steps needed to go from written to sounding pitch. This allows for correct spelling of enharmonic transpositions. This value does not include octave-change values; the values for both elements need to be added to the written pitch to get the correct sounding pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLChromatic(XMLElement):
    
    TYPE = XSDSimpleTypeSemitones
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="chromatic" type="semitones">
    <xs:annotation>
        <xs:documentation>The chromatic element represents the number of semitones needed to get from written to sounding pitch. This value does not include octave-change values; the values for both elements need to be added to the written pitch to get the correct sounding pitch.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLOctaveChange(XMLElement):
    
    TYPE = XSDSimpleTypeInteger
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="octave-change" type="xs:integer" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The octave-change element indicates how many octaves to add to get from written pitch to sounding pitch. The octave-change element should be included when using transposition intervals of an octave or more, and should not be present for intervals of less than an octave.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDouble(XMLElement):
    
    TYPE = XSDComplexTypeDouble
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="double" type="double" minOccurs="0">
    <xs:annotation>
        <xs:documentation>If the double element is present, it indicates that the music is doubled one octave from what is currently written.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeatUnit(XMLElement):
    
    TYPE = XSDSimpleTypeNoteTypeValue
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beat-unit" type="note-type-value">
    <xs:annotation>
        <xs:documentation>The beat-unit element indicates the graphical note type to use in a metronome mark.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBeatUnitDot(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="beat-unit-dot" type="empty" minOccurs="0" maxOccurs="unbounded">
    <xs:annotation>
        <xs:documentation>The beat-unit-dot element is used to specify any augmentation dots for a metronome mark note.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRoot(XMLElement):
    
    TYPE = XSDComplexTypeRoot
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="root" type="root" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNumeral(XMLElement):
    
    TYPE = XSDComplexTypeNumeral
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="numeral" type="numeral" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFunction(XMLElement):
    
    TYPE = XSDComplexTypeStyleText
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="function" type="style-text">
    <xs:annotation>
        <xs:documentation>The function element represents classical functional harmony with an indication like I, II, III rather than C, D, E. It represents the Roman numeral part of a functional harmony rather than the complete function itself. It has been deprecated as of MusicXML 4.0 in favor of the numeral element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLKind(XMLElement):
    
    TYPE = XSDComplexTypeKind
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="kind" type="kind" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLInversion(XMLElement):
    
    TYPE = XSDComplexTypeInversion
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="inversion" type="inversion" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBass(XMLElement):
    
    TYPE = XSDComplexTypeBass
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bass" type="bass" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDegree(XMLElement):
    
    TYPE = XSDComplexTypeDegree
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="degree" type="degree" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLTopMargin(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="top-margin" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBottomMargin(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="bottom-margin" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPageLayout(XMLElement):
    
    TYPE = XSDComplexTypePageLayout
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="page-layout" type="page-layout" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLSystemLayout(XMLElement):
    
    TYPE = XSDComplexTypeSystemLayout
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="system-layout" type="system-layout" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLStaffLayout(XMLElement):
    
    TYPE = XSDComplexTypeStaffLayout
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="staff-layout" type="staff-layout" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLLeftMargin(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="left-margin" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRightMargin(XMLElement):
    
    TYPE = XSDSimpleTypeTenths
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="right-margin" type="tenths" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDuration(XMLElement):
    
    TYPE = XSDSimpleTypePositiveDivisions
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="duration" type="positive-divisions">
    <xs:annotation>
        <xs:documentation>Duration is a positive number specified in division units. This is the intended duration vs. notated duration (for instance, differences in dotted notes in Baroque-era music). Differences in duration specific to an interpretation or performance should be represented using the note element's attack and release attributes.

The duration element moves the musical position when used in backup elements, forward elements, and note elements that do not contain a chord child element.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDisplayStep(XMLElement):
    
    TYPE = XSDSimpleTypeStep
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="display-step" type="step" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDisplayOctave(XMLElement):
    
    TYPE = XSDSimpleTypeOctave
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="display-octave" type="octave" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLChord(XMLElement):
    
    TYPE = XSDComplexTypeEmpty
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="chord" type="empty" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The chord element indicates that this note is an additional chord tone with the preceding note.

The duration of a chord note does not move the musical position within a measure. That is done by the duration of the first preceding note without a chord element. Thus the duration of a chord note cannot be longer than the preceding note.
							
In most cases the duration will be the same as the preceding note. However it can be shorter in situations such as multiple stops for string instruments.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPitch(XMLElement):
    
    TYPE = XSDComplexTypePitch
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="pitch" type="pitch" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLUnpitched(XMLElement):
    
    TYPE = XSDComplexTypeUnpitched
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="unpitched" type="unpitched" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLRest(XMLElement):
    
    TYPE = XSDComplexTypeRest
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="rest" type="rest" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLNote(XMLElement):
    
    TYPE = XSDComplexTypeNote
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="note" type="note" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBackup(XMLElement):
    
    TYPE = XSDComplexTypeBackup
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="backup" type="backup" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLForward(XMLElement):
    
    TYPE = XSDComplexTypeForward
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="forward" type="forward" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDirection(XMLElement):
    
    TYPE = XSDComplexTypeDirection
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="direction" type="direction" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLAttributes(XMLElement):
    
    TYPE = XSDComplexTypeAttributes
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="attributes" type="attributes" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLHarmony(XMLElement):
    
    TYPE = XSDComplexTypeHarmony
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="harmony" type="harmony" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLFiguredBass(XMLElement):
    
    TYPE = XSDComplexTypeFiguredBass
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="figured-bass" type="figured-bass" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPrint(XMLElement):
    
    TYPE = XSDComplexTypePrint
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="print" type="print" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLBarline(XMLElement):
    
    TYPE = XSDComplexTypeBarline
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="barline" type="barline" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLGrouping(XMLElement):
    
    TYPE = XSDComplexTypeGrouping
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="grouping" type="grouping" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartGroup(XMLElement):
    
    TYPE = XSDComplexTypePartGroup
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-group" type="part-group" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLWork(XMLElement):
    
    TYPE = XSDComplexTypeWork
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="work" type="work" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMovementNumber(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="movement-number" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The movement-number element specifies the number of a movement.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLMovementTitle(XMLElement):
    
    TYPE = XSDSimpleTypeString
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="movement-title" type="xs:string" minOccurs="0">
    <xs:annotation>
        <xs:documentation>The movement-title element specifies the title of a movement, not including its number.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLDefaults(XMLElement):
    
    TYPE = XSDComplexTypeDefaults
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="defaults" type="defaults" minOccurs="0" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLCredit(XMLElement):
    
    TYPE = XSDComplexTypeCredit
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="credit" type="credit" minOccurs="0" maxOccurs="unbounded" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLPartList(XMLElement):
    
    TYPE = XSDComplexTypePartList
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="part-list" type="part-list" />
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()


class XMLScorePart(XMLElement):
    
    TYPE = XSDComplexTypeScorePart
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:element xmlns:xs="http://www.w3.org/2001/XMLSchema" name="score-part" type="score-part">
    <xs:annotation>
        <xs:documentation>Each MusicXML part corresponds to a track in a Standard MIDI Format 1 file. The score-instrument elements are used when there are multiple instruments per track. The midi-device element is used to make a MIDI device or port assignment for the given track. Initial midi-instrument assignments may be made here as well.</xs:documentation>
    </xs:annotation>
</xs:element>
"""
                                     ))

    @property
    def __doc__(self):
        if self.TYPE.XSD_TREE.is_complex_type:
            return self.TYPE.__doc__
        else:
            return self.XSD_TREE.get_doc()

__all__=['XMLScorePartwise', 'XMLPart', 'XMLMeasure', 'XMLDirective', 'XMLP', 'XMLPp', 'XMLPpp', 'XMLPppp', 'XMLPpppp', 'XMLPppppp', 'XMLF', 'XMLFf', 'XMLFff', 'XMLFfff', 'XMLFffff', 'XMLFfffff', 'XMLMp', 'XMLMf', 'XMLSf', 'XMLSfp', 'XMLSfpp', 'XMLFp', 'XMLRf', 'XMLRfz', 'XMLSfz', 'XMLSffz', 'XMLFz', 'XMLN', 'XMLPf', 'XMLSfzp', 'XMLOtherDynamics', 'XMLMidiChannel', 'XMLMidiName', 'XMLMidiBank', 'XMLMidiProgram', 'XMLMidiUnpitched', 'XMLVolume', 'XMLPan', 'XMLElevation', 'XMLDisplayText', 'XMLAccidentalText', 'XMLIpa', 'XMLMute', 'XMLSemiPitched', 'XMLOtherPlay', 'XMLDivisions', 'XMLKey', 'XMLTime', 'XMLStaves', 'XMLPartSymbol', 'XMLInstruments', 'XMLClef', 'XMLStaffDetails', 'XMLTranspose', 'XMLForPart', 'XMLMeasureStyle', 'XMLPartClef', 'XMLPartTranspose', 'XMLTimeRelation', 'XMLKeyOctave', 'XMLMultipleRest', 'XMLMeasureRepeat', 'XMLBeatRepeat', 'XMLSlash', 'XMLStaffType', 'XMLStaffLines', 'XMLLineDetail', 'XMLStaffTuning', 'XMLCapo', 'XMLStaffSize', 'XMLInterchangeable', 'XMLSenzaMisura', 'XMLBarStyle', 'XMLWavyLine', 'XMLSegno', 'XMLCoda', 'XMLFermata', 'XMLEnding', 'XMLRepeat', 'XMLAccordionHigh', 'XMLAccordionMiddle', 'XMLAccordionLow', 'XMLBassSeparator', 'XMLBassStep', 'XMLBassAlter', 'XMLDegreeValue', 'XMLDegreeAlter', 'XMLDegreeType', 'XMLDirectionType', 'XMLOffset', 'XMLSound', 'XMLListening', 'XMLRehearsal', 'XMLWords', 'XMLSymbol', 'XMLWedge', 'XMLDynamics', 'XMLDashes', 'XMLBracket', 'XMLPedal', 'XMLMetronome', 'XMLOctaveShift', 'XMLHarpPedals', 'XMLDamp', 'XMLDampAll', 'XMLEyeglasses', 'XMLStringMute', 'XMLScordatura', 'XMLImage', 'XMLPrincipalVoice', 'XMLPercussion', 'XMLAccordionRegistration', 'XMLStaffDivide', 'XMLOtherDirection', 'XMLFrameStrings', 'XMLFrameFrets', 'XMLFirstFret', 'XMLFrameNote', 'XMLString', 'XMLFret', 'XMLFingering', 'XMLBarre', 'XMLFeature', 'XMLFrame', 'XMLPedalTuning', 'XMLSync', 'XMLOtherListening', 'XMLBeatUnitTied', 'XMLPerMinute', 'XMLMetronomeArrows', 'XMLMetronomeNote', 'XMLMetronomeRelation', 'XMLMetronomeType', 'XMLMetronomeDot', 'XMLMetronomeBeam', 'XMLMetronomeTied', 'XMLMetronomeTuplet', 'XMLNumeralRoot', 'XMLNumeralAlter', 'XMLNumeralKey', 'XMLNumeralFifths', 'XMLNumeralMode', 'XMLPedalStep', 'XMLPedalAlter', 'XMLGlass', 'XMLMetal', 'XMLWood', 'XMLPitched', 'XMLMembrane', 'XMLEffect', 'XMLTimpani', 'XMLBeater', 'XMLStick', 'XMLStickLocation', 'XMLOtherPercussion', 'XMLMeasureLayout', 'XMLMeasureNumbering', 'XMLPartNameDisplay', 'XMLPartAbbreviationDisplay', 'XMLRootStep', 'XMLRootAlter', 'XMLAccord', 'XMLInstrumentChange', 'XMLMidiDevice', 'XMLMidiInstrument', 'XMLPlay', 'XMLSwing', 'XMLStickType', 'XMLStickMaterial', 'XMLStraight', 'XMLFirst', 'XMLSecond', 'XMLSwingType', 'XMLSwingStyle', 'XMLEncodingDate', 'XMLEncoder', 'XMLSoftware', 'XMLEncodingDescription', 'XMLSupports', 'XMLCreator', 'XMLRights', 'XMLEncoding', 'XMLSource', 'XMLRelation', 'XMLMiscellaneous', 'XMLMiscellaneousField', 'XMLLineWidth', 'XMLNoteSize', 'XMLDistance', 'XMLGlyph', 'XMLOtherAppearance', 'XMLMeasureDistance', 'XMLPageHeight', 'XMLPageWidth', 'XMLPageMargins', 'XMLMillimeters', 'XMLTenths', 'XMLStaffDistance', 'XMLLeftDivider', 'XMLRightDivider', 'XMLSystemMargins', 'XMLSystemDistance', 'XMLTopSystemDistance', 'XMLSystemDividers', 'XMLAccent', 'XMLStrongAccent', 'XMLStaccato', 'XMLTenuto', 'XMLDetachedLegato', 'XMLStaccatissimo', 'XMLSpiccato', 'XMLScoop', 'XMLPlop', 'XMLDoit', 'XMLFalloff', 'XMLBreathMark', 'XMLCaesura', 'XMLStress', 'XMLUnstress', 'XMLSoftAccent', 'XMLOtherArticulation', 'XMLArrowDirection', 'XMLArrowStyle', 'XMLArrowhead', 'XMLCircularArrow', 'XMLBendAlter', 'XMLPreBend', 'XMLRelease', 'XMLWithBar', 'XMLPrefix', 'XMLFigureNumber', 'XMLSuffix', 'XMLExtend', 'XMLFigure', 'XMLHarmonClosed', 'XMLNatural', 'XMLArtificial', 'XMLBasePitch', 'XMLTouchingPitch', 'XMLSoundingPitch', 'XMLHoleType', 'XMLHoleClosed', 'XMLHoleShape', 'XMLAssess', 'XMLWait', 'XMLOtherListen', 'XMLSyllabic', 'XMLText', 'XMLElision', 'XMLLaughing', 'XMLHumming', 'XMLEndLine', 'XMLEndParagraph', 'XMLTied', 'XMLSlur', 'XMLTuplet', 'XMLGlissando', 'XMLSlide', 'XMLOrnaments', 'XMLTechnical', 'XMLArticulations', 'XMLArpeggiate', 'XMLNonArpeggiate', 'XMLAccidentalMark', 'XMLOtherNotation', 'XMLGrace', 'XMLTie', 'XMLCue', 'XMLInstrument', 'XMLType', 'XMLDot', 'XMLAccidental', 'XMLTimeModification', 'XMLStem', 'XMLNotehead', 'XMLNoteheadText', 'XMLBeam', 'XMLNotations', 'XMLLyric', 'XMLListen', 'XMLTrillMark', 'XMLTurn', 'XMLDelayedTurn', 'XMLInvertedTurn', 'XMLDelayedInvertedTurn', 'XMLVerticalTurn', 'XMLInvertedVerticalTurn', 'XMLShake', 'XMLMordent', 'XMLInvertedMordent', 'XMLSchleifer', 'XMLTremolo', 'XMLHaydn', 'XMLOtherOrnament', 'XMLStep', 'XMLAlter', 'XMLOctave', 'XMLUpBow', 'XMLDownBow', 'XMLHarmonic', 'XMLOpenString', 'XMLThumbPosition', 'XMLPluck', 'XMLDoubleTongue', 'XMLTripleTongue', 'XMLStopped', 'XMLSnapPizzicato', 'XMLHammerOn', 'XMLPullOff', 'XMLBend', 'XMLTap', 'XMLHeel', 'XMLToe', 'XMLFingernails', 'XMLHole', 'XMLArrow', 'XMLHandbell', 'XMLBrassBend', 'XMLFlip', 'XMLSmear', 'XMLOpen', 'XMLHalfMuted', 'XMLHarmonMute', 'XMLGolpe', 'XMLOtherTechnical', 'XMLActualNotes', 'XMLNormalNotes', 'XMLNormalType', 'XMLNormalDot', 'XMLTupletActual', 'XMLTupletNormal', 'XMLTupletNumber', 'XMLTupletType', 'XMLTupletDot', 'XMLCreditType', 'XMLLink', 'XMLBookmark', 'XMLCreditImage', 'XMLCreditWords', 'XMLCreditSymbol', 'XMLScaling', 'XMLConcertScore', 'XMLAppearance', 'XMLMusicFont', 'XMLWordFont', 'XMLLyricFont', 'XMLLyricLanguage', 'XMLGroupName', 'XMLGroupNameDisplay', 'XMLGroupAbbreviation', 'XMLGroupAbbreviationDisplay', 'XMLGroupSymbol', 'XMLGroupBarline', 'XMLGroupTime', 'XMLInstrumentLink', 'XMLGroupLink', 'XMLPlayerName', 'XMLInstrumentName', 'XMLInstrumentAbbreviation', 'XMLIdentification', 'XMLPartLink', 'XMLPartName', 'XMLPartAbbreviation', 'XMLGroup', 'XMLScoreInstrument', 'XMLPlayer', 'XMLVirtualLibrary', 'XMLVirtualName', 'XMLWorkNumber', 'XMLWorkTitle', 'XMLOpus', 'XMLFootnote', 'XMLLevel', 'XMLStaff', 'XMLTuningStep', 'XMLTuningAlter', 'XMLTuningOctave', 'XMLInstrumentSound', 'XMLSolo', 'XMLEnsemble', 'XMLVirtualInstrument', 'XMLVoice', 'XMLSign', 'XMLLine', 'XMLClefOctaveChange', 'XMLKeyStep', 'XMLKeyAlter', 'XMLKeyAccidental', 'XMLSlashType', 'XMLSlashDot', 'XMLExceptVoice', 'XMLBeats', 'XMLBeatType', 'XMLCancel', 'XMLFifths', 'XMLMode', 'XMLDiatonic', 'XMLChromatic', 'XMLOctaveChange', 'XMLDouble', 'XMLBeatUnit', 'XMLBeatUnitDot', 'XMLRoot', 'XMLNumeral', 'XMLFunction', 'XMLKind', 'XMLInversion', 'XMLBass', 'XMLDegree', 'XMLTopMargin', 'XMLBottomMargin', 'XMLPageLayout', 'XMLSystemLayout', 'XMLStaffLayout', 'XMLLeftMargin', 'XMLRightMargin', 'XMLDuration', 'XMLDisplayStep', 'XMLDisplayOctave', 'XMLChord', 'XMLPitch', 'XMLUnpitched', 'XMLRest', 'XMLNote', 'XMLBackup', 'XMLForward', 'XMLDirection', 'XMLAttributes', 'XMLHarmony', 'XMLFiguredBass', 'XMLPrint', 'XMLBarline', 'XMLGrouping', 'XMLPartGroup', 'XMLWork', 'XMLMovementNumber', 'XMLMovementTitle', 'XMLDefaults', 'XMLCredit', 'XMLPartList', 'XMLScorePart']
