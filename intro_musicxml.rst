musicxml
*********

The central class of this package is the :obj:`~musicxml.xmlelement.xmlelement.XMLElement` class which is the parent of each individual
xml element class (like XMLScore, XMLPart etc.). The xml element classes (mainly created automatically) behave exactly as declared in the
musicxml schema file. The ``type_`` of Each :obj:`~musicxml.xmlelement.xmlelement.XMLElement` class is set to :obj:`~musicxml.xsd.xsdcomplextype.XSDComplexType` or :obj:`~musicxml.xsd.xsdsimpletype.XSDSimpleType` which correspond to xml schema elements ``complexType``
and ``simpleType``.

The documentation of this package covers only the information given in the musicxml schema file, including the structure of possible or
necessary children and attributes indicated by xsd elements and and cannot replace the more comprehensive documentation of `W3C Community Group <https://www.w3.org/2021/06/musicxml40/>`_ . The topic of xml and xml schema goes beyond the scope of this documentation. For further information see `here <https://www.w3schools.com/xml/default.asp>`_

Each musicxml element can be created as an instance of a class which behaves (hopefully exactly!) as the musicxml schema
(version 4, see ``musicxml_4_0.xsd`` in ``musicxml.generate_classes``) specifies, e.g.:

..  code:: Python

    pitch = XMLPitch()

Children can be added with method add_child(<xmlelement>):

..  code:: Python

    pitch.add_child(XMLStep('G'))


As a shortcut it is possible to add, remove or change child with a dot operator:

..  code:: Python

    pitch.xml_step = 'G'

is equivalent to:

..  code:: Python

    pitch.xml_step = XMLStep('G')

change:

..  code:: Python

    pitch.xml_step = 'F'


or remove:

..  code:: Python

    pitch.xml_step = None

Dot operator can also be used as a shortcut to get a child:

..  code:: Python

    print(pitch.xml_step.value)


The value of an element (which be translated to text of xml element) can be set during or after creation:

octave = pitch.add_child(XMLOctave())

..  code:: Python

    octave.value = 3

Attributes also can be added during or after creation:

..  code:: Python

    font = XMLFont(font_family='Arial')
    font.font_size = 17.2


An existing musicxml file can be parsed easily with parser's ``parse_musicxml(file_path)`` function.

Each element creates a rather complicated tree format container with xsd indicator objects (XSDSequence, XSDChoice, XSDGroup, XSDElement)
which represent their counterparts in a xsd structure to validate and order its children (take a peek inside the file musicxml_4_0.xsd in
musicxml.generate_classes to get a feeling for its complexity). If a child is going to be added to an element it tries to 'hook' this child
inside a XSDElement leaf of this container tree which has the same name as the child. For elements which use a choice indicator (XSDChoice)
it can happen, that the current chosen path throws an error since this particular path does not have a XSDElement leaf with child's name, or
it could for example require another not existing child in the final check. It these cases the parent element tries to attach its children
to another choice path and see if the problem can be solved. On this account although some thorough testings have been done, there is yet no
guaranty that in some cases the library does not behave as it should. Please let me know if you discover a bug!

A variety of errors might be thrown during creating an object (for example if you try to add a child of a wrong type or to add a wrong
attribute)
. The method to_string() calls an intern final check before exporting the xml element to a string to be sure you didn't forget any required
children and attributes.

If attribute ``xsd_check`` is set to ``False`` not xsd checking take place during adding a child or calling ``to_string()`` method. In this case
children will be added to parent in the same order as adding did take place. If ``xsd_check`` is set to ``True`` ordering will be according to
musicxmls xsd structure.


The SOURCECODE can be found on Github: https://github.com/alexgorji/musicxml