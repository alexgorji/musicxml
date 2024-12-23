# Version 0.1.2

This version is the first uploaded version to PyPI

# Version 0.1.3

`XMLElement` dot operator: shorthand to set and get a child `XMLElement.Type`: a class attribute to set ComplexType for
an `XMLElement`.

Bug fix: `XMLElement._SIMPLE_CONTENT`: is used to validate value. Using XSDSimpleTypes as parent was not the right way
to achieve this
validation

`XMLElement.<attribute> = None`: removes attribute if needed.

`XMLElement.remove(<child XMLElement>)`: removes child

`XMLElement XMLElement._unordered_children`: list to accelerate finding children if order of children is not important

`XMLElement.get_children(ordered=True)`: ordered False returns XMLElement._unordered_children

`XMLElement.find_child(ordered=False)` and `XMLElement.find_children(ordered=False)` added.

# Version 0.1.4

`README.md` is updated to include XMLElement dot operators as shorthand for getting or setting a child.

doc strings added to `XMLElement`

`XMLElement.get_class_name()`: removed. Use `XMLElement.__class__.__name__` instead

Bug fix: `XMLElement.get_parent()`: if XMLElement is a child returns now the parent XMLElement.
`Tree.up`: returns `Tree.get_parent()`
Bug fix: `XMLElement.remove(<child>)` removes duplications in `ChildContainerTree` if necessary. Bug
fix: `XMLElement.value` can be set to
None.
`Tree.get_leaves()`: added

Bug fix: `XMLElement.remove()`: remove_duplicate is now called after removing child. Indentation: changed from 4 spaced
to 2 spaces in order
to be consistent with finale's musicxml export.

Bug fix: `XMLChildContainer.add_element()`: if container has a parent_element and container gets a duplicated parent,
duplicated parent
replaces parent_element's container if needed. (Necessary for `XMLArticulations`)

`XMLElement.value` renamed to `XMLElement.value_`
`XMLElement.value_` will be checked immediately also for XSDComplexTypes

`XMLElement._check_value()` sets `self.TYPE.element` to self
`XSDComplexType` and `XSDSimpleType`: `element` attribute and `_get_error_class()` method added to be able to give a
better error message.
error messages improved.

# Version 0.1.5

Bug fix: `XMLChildContainer.add_element()`: if container has a parent_element and container gets a duplicated parent,
duplicated parent
replaces parent_element's container if needed. (Necessary for `XMLEncoding`)

# Version 1.0

Release together with musicscore2

# Version 1.1

`XMLElement.xsd_check `attribute added.
`XMLElement.replace_child` returns new child
`XMLSenzaMisura` with default value "" in order to be optional.

# Version 1.1.1

`README.rst`
`intro_musicxml.rst`
`usage.rst`

# Version 1.2

performance optimisation: `XMLElment.xsd_tree` is only initiated the first time the class is initiated to avoid using
find function in
xml.etree.Element to often.

# Version 1.3

performance optimisation: tree.traverse(), iter_leaves(), reversed_path_to_root() are being cached. To reset call
tree._reset_iterators()
performance optimisation: tree.is_leaf is not checked each time. tree.add_chord() sets parten's is_leaf to False
performance optimisation: xsdcomplextype _XSD_ATTRIBUTES added. This class attribute will be filled only once which
improves XSDComplexType.get_xsd_attributes() method.

# Version 1.3.1

``XSD_TREE_DICT`` is now used for generating all classes. No performance optimization but a bit tidier.
``__copy__`` added to indicators
``XMLElement.value_`` default value set to '' instead of None
``xmlchildcontainer.requirements_not_fulfilled`` renamed and refactored to ``requirements_fulfilled``
bug fix: if sequene has maxOccur==unbounded parent can be duplicated.

~~# Version 1.3.2
bug fix: ``tree.Tree._reset_iterators()`` has not been added to PyPi package. Via pip installed 'musicscore2' couldn't
work.~~

# Version 1.3.3

``musicxml import *`` imports ``from musicxml.xmlelement.xmlelement import *``
``tree.Tree.get_children_of_type(type_)`` added
Bug fix: `:obj:`~musicxml.xmlelement.xmlelement._final_checks()`` runs only if xsd_check is set to True.

# Version 1.4
get_children_of_type() type_ replaced with type to avoid conflict with rtd
reset_frozen renamed to _reset_iterators
get_indentation renamed to _get_indentation
Tree documention link added to public properties and methods

# Verision 1.4.1
avoid warnings

# Version 1.5
Using verysimpletree library
!!generating classes still not tested!!

# Version 1.6
add __deepcopy__ to XMLElement
!!generating classes still not tested!!