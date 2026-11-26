# musicxml

`musicxml` is a Python library for creating MusicXML data. Its
element classes are based on the MusicXML 4.0 XML schema, providing an
object-oriented way to build and inspect MusicXML trees.

The library is also a dependency of [musicscore](https://github.com/alexgorji/musicscore),
which offers a higher-level API for creating scores.

## Features

- Create MusicXML elements, attributes, and child elements as Python objects.
- Check element structure and order children using MusicXML schema definitions.
- Serialize elements to XML.

## Installation

Requires Python 3.11 or newer:

```console
python -m pip install musicxml
```

## Quick start

Create a pitch with a step and an octave:

```python
from musicxml.xmlelement.xmlelement import XMLOctave, XMLPitch, XMLStep

pitch = XMLPitch()
pitch.add_child(XMLStep("G"))
pitch.add_child(XMLOctave(4))

print(pitch.to_string())
```

This prints:

```xml
<pitch>
  <step>G</step>
  <octave>4</octave>
</pitch>
```

You can also access or update children using attributes:

```python
pitch.xml_step = "F"
print(pitch.xml_step.value_)
```

`to_string()` checks required children and attributes before serialization.
Schema choices can be complex, so this should not be treated as a guarantee
that every possible MusicXML document is handled correctly.

## Documentation

See the [documentation source](docs/source/index.rst) and the
[MusicXML 4.0 specification](https://www.w3.org/2021/06/musicxml40/).
For a higher-level score-building API, see the
[musicscore documentation](https://musicscore.readthedocs.io).

## Development

Install the test dependencies and run the test suite with Poetry:

```console
poetry install --with test
poetry run pytest
```

## License

MIT. See [LICENSE](LICENSE).
