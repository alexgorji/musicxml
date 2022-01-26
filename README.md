musicxml is a python library for reading and writing musicxml files.

INSTALLATION

1. Check the version of python on your computer: `python --version`. This library has been developed with python 3.9. Possibly you have to
   install this version (for example via Homebrew or whatever way you choose.)

2. Make a new folder and create a virtual environment for your project and install musicxml via pip:
    * mkdir <project>
    * cd <project>
    * python3 -m venv venv
    * source venv/bin/activate
    * pip install --upgrade pip
    * pip install musicxml

The SOURCECODE can be found on Github: https://github.com/alexgorji/musicxml

Each musicxml element can be created as an instance of a class which behaves (hopefully exactly!) as the musicxml schema
(version 4, see musicxml_4_0.xsd in musicxml.generate_classes) specifies, e.g.:

```
pitch = XMLPitch()
```

Children can be added with method add_child(<xmlelement>):

```
pitch.add_child(XMLStep('G'))
```

As a shortcut it is possible to add, remove or change child with a dot operator:

```
pitch.xml_step = 'G'
```

is equivalent to:

```
pitch.xml_step = XMLStep('G')
```

change:

```
pitch.xml_step = 'F'
```

or remove:

```
pitch.xml_step = None
```

Dot operator can also be used as a shortcut to get a child:

```
print(pitch.xml_step.value)
```

The value of an element (which be translated to text of xml element) can be set during or after creation:

```
octave = pitch.add_child(XMLOctave())
octave.value = 3
```

Attributes also can be added during or after creation:

```
font = XMLFont(font_family='Arial')
font.font_size = 17.2
```

A variety of errors are thrown during creating an object (for example if you try to add a child of a wrong type or to add a wrong attribute)
. The method to_string() calls an intern final check before exporting the xml element to a string to be sure you didn't forget any required
children and attributes.

An existing musicxml file can be parsed easily with parser's parse_musicxml(file_path) function.

Each element creates a rather complicated tree format container with xsd indicator objects (XSDSequence, XSDChoice, XSDGroup, XSDElement)
which represent their counterparts in a xsd structure to validate and order its children (take a peek inside the file musicxml_4_0.xsd in
musicxml.generate_classes to get a feeling for its complexity). If a child is going to be added to an element it tries to 'hook' this child
inside a XSDElement leaf of this container tree which has the same name as the child. For elements which use a choice indicator (XSDChoice)
it can happen, that the current chosen path throws an error since this particular path does not have a XSDElement leaf with child's name, or
it could for example require another not existing child in the final check. It these cases the parent element tries to attach its children
to another choice path and see if the problem can be solved. On this account although some thorough testings have been done, there is yet no
guaranty that in some cases the library does not behave as it should. Please let me know if you discover a bug!

A musicxml file can get easily very long (see for example Bach's piano partita no. 3 in parser with 126327 lines!). The parser manages to
read the whole file in about 1 minutes on my machine. Maybe it can get faster in the future ...

At the moment no documentation exists. But you can use the very extensive musicxml documentation
on: [https://www.w3. org/2021/06/musicxml40/](https://www.w3.org/2021/06/musicxml40/)