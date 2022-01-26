# Version 0.1.2

This version is the first uploaded version to PyPi

# Version 0.1.3

`XMLElement` dot operator: shorthand to set and get a child `XMLElement.Type`: a class attribute to set ComplexType for an `XMLElement`.

Bug fix: `XMLElement._SIMPLE_CONTENT`: is used to validate value. Using XSDSimpleTypes as parent was not the right way to achieve this
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