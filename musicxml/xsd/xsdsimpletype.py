import re
import xml.etree.ElementTree as ET
from typing import Any, Optional

from musicxml.util.core import get_cleaned_token
from musicxml.xsd.xsdtree import XSDTree, XSDTreeElement, XSD_TREE_DICT


class XSDSimpleType(XSDTreeElement):
    """
    Parent Class for all SimpleType classes
    """
    _TYPES: list[type] = []
    _UNION: list[Any] = []
    _FORCED_PERMITTED: list[str] = []
    _PERMITTED: list[str] = []
    _PATTERN: Optional[str] = None

    def __init__(self, value: Any, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        if not self._PERMITTED:
            self._populate_permitted()
        if not self._FORCED_PERMITTED:
            self._populate_forced_permitted()
        if self._UNION:
            self._TYPES = []
            for t_ in self._UNION:
                self._TYPES.extend(t_._TYPES)
        self._populate_pattern()
        self._value = None
        self.value = value

    def _check_value(self, v):
        if self._UNION:
            errors = []
            for t_ in self._UNION:
                try:
                    t_(v)
                    return
                except TypeError:
                    pass
                except ValueError as err:
                    errors.append(err.args[0])
            raise ValueError(self._get_error_class(), errors)

        elif v in self._FORCED_PERMITTED:
            return
        if self._PERMITTED:
            if v not in self._PERMITTED:
                raise ValueError(f"{self._get_error_class()}.value '{v}' must be in {self._PERMITTED}")
        elif self._PATTERN:
            restriction = self.get_xsd_tree().get_restriction()
            if restriction:
                if restriction.get_attributes()['base'] == 'xs:date':
                    XSDSimpleTypeDate(v)
                elif restriction.get_attributes()['base'] == 'xs:token':
                    v = XSDSimpleTypeToken(v).value
                elif restriction.get_attributes()['base'] == 'xs:smufl-glyph-name':
                    XSDSimpleTypeSmuflGlyphName(v)
            if re.compile(self._PATTERN).fullmatch(v) is None:
                raise ValueError(
                    f"{self._get_error_class()}.value '{v}' must match the following pattern: {self._PATTERN}")
        else:
            restriction = self.get_xsd_tree().get_restriction()
            if restriction:
                restriction_children = restriction.get_children()
                for child in restriction_children:
                    if child.tag == 'minLength' and len(v) < int(child.get_attributes()['value']):
                        raise ValueError(
                            f"{self._get_error_class()}.value '{v}' must have a length >= 1")
                    if child.tag == 'minExclusive' and v <= int(child.get_attributes()['value']):
                        raise ValueError(
                            f"{self._get_error_class()}.value '{v}' must be greater than"
                            f" '{child.get_attributes()['value']}'")
                    if child.tag == 'minInclusive' and v < int(child.get_attributes()['value']):
                        raise ValueError(
                            f"{self._get_error_class()}.value '{v}' must be greater than or equal to"
                            f" '{child.get_attributes()['value']}'")
                    if child.tag == 'maxInclusive' and v > int(child.get_attributes()['value']):
                        raise ValueError(
                            f"{self._get_error_class()}.value '{v}' must be less than or equal to"
                            f" '{child.get_attributes()['value']}'")

    def _check_value_type(self, value):
        if value in self._FORCED_PERMITTED:
            return
        if isinstance(self._TYPES, str):
            raise TypeError
        if self._TYPES == str or not hasattr(self._TYPES, '__iter__'):
            raise TypeError

        if True in [isinstance(value, type_) for type_ in self._TYPES]:
            pass
        else:
            message = f"{self._get_error_class()}'s value '{value}' can only be of types {[type_.__name__ for type_ in self._TYPES]} not {type(value).__name__}."
            if self._PERMITTED:
                message += f" {self._get_error_class()}.value must in {self._PERMITTED}"
            if self._FORCED_PERMITTED:
                message += f" {self._get_error_class()}.value can also be {self._FORCED_PERMITTED}"
            raise TypeError(message)

    def _get_error_class(self):
        if self.parent:
            return self.parent.__class__.__name__
        else:
            return self.__class__.__name__

    def _populate_permitted(self):
        self._PERMITTED = self.get_xsd_tree().get_permitted()

    def _populate_forced_permitted(self):
        union = self.get_xsd_tree().get_union()
        if union and union.get_children() and union.get_children()[0].tag == 'simpleType':
            intern_simple_type = union.get_children()[0]
            enumerations = [child for child in intern_simple_type.get_restriction().get_children() if child.tag
                            == 'enumeration']
            self._FORCED_PERMITTED = [enumeration.get_attributes()['value'] for enumeration in enumerations]

    def _populate_pattern(self):
        pattern = self.get_xsd_tree().get_pattern(self.__class__.__mro__[1].get_xsd_tree())
        if pattern:
            self._PATTERN = pattern

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._check_value_type(v)
        if v not in self._FORCED_PERMITTED:
            self._check_value(v)
        self._value = v

    def __repr__(self):
        return str(self.value)


class XSDSimpleTypeInteger(XSDSimpleType):
    _TYPES = [int]
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="integer" id="integer">
            <xs:restriction base="xs:decimal">
                <xs:fractionDigits value="0" fixed="true"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        self._check_value_type(v)
        super(XSDSimpleTypeInteger, type(self)).value.fset(self, v)


class XSDSimpleTypeNonNegativeInteger(XSDSimpleTypeInteger):
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="nonNegativeInteger" id="nonNegativeInteger">
            <xs:restriction base="xs:integer">
                <xs:minInclusive value="0"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        super(XSDSimpleTypeNonNegativeInteger, type(self)).value.fset(self, v)
        if v < 0:
            raise ValueError(f'value {v} must be non negative.')


class XSDSimpleTypePositiveInteger(XSDSimpleTypeInteger):
    _TYPES = [int]
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="positiveInteger" id="positiveInteger">
            <xs:restriction base="xs:nonNegativeInteger">
                <xs:minInclusive value="1"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        super(XSDSimpleTypePositiveInteger, type(self)).value.fset(self, v)
        try:
            if v <= 0:
                raise ValueError(f'value {v} must be greater than 0.')
        except TypeError:
            # Important because of XSDSimpleTypePositiveIntegerOrEmpty
            pass


class XSDSimpleTypeDecimal(XSDSimpleType):
    _TYPES = [float, int]
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="decimal" id="decimal">
            <xs:restriction base="xs:anySimpleType">
                <xs:whiteSpace value="collapse" fixed="true"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        self._check_value_type(v)
        super(XSDSimpleTypeDecimal, type(self)).value.fset(self, v)


class XSDSimpleTypeString(XSDSimpleType):
    _TYPES = [str]
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="string" id="string">
            <xs:restriction base="xs:anySimpleType">
                <xs:whiteSpace value="preserve"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        self._check_value_type(v)
        super(XSDSimpleTypeString, type(self)).value.fset(self, v)


class XSDSimpleTypeToken(XSDSimpleTypeString):
    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="token" id="token">
            <xs:restriction base="xs:normalizedString">
                <xs:whiteSpace value="collapse"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))

    @property
    def value(self):
        return super().value

    @value.setter
    def value(self, v):
        super(XSDSimpleTypeToken, type(self)).value.fset(self, v)
        v = get_cleaned_token(v)
        self._value = v


class XSDSimpleTypeDate(XSDSimpleTypeString):
    # [-]CCYY-MM-DD[Z|(+|-)hh:mm]
    # https://www.oreilly.com/library/view/regular-expressions-cookbook/9781449327453/ch04s07.html

    _XSD_TREE = XSDTree(ET.fromstring(
        """
        <xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="date" id="date">
            <xs:restriction base="xs:anySimpleType">
                <xs:whiteSpace value="collapse" fixed="true"/>
            </xs:restriction>
        </xs:simpleType>
        """
    ))
    _PATTERN = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])(Z|[+-](?:2[0-3]|[01][0-9]):[' \
               r'0-5][0-9])?$'

# -----------------------------------------------------
# AUTOMATICALLY GENERATED WITH generate_simple_types.py
# -----------------------------------------------------


class XSDSimpleTypeNMTOKEN(XSDSimpleTypeToken):
    """
    
        
Pattern: [-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]+
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['NMTOKEN']


class XSDSimpleTypeName(XSDSimpleTypeToken):
    """
    
        
Pattern: [:A-Z_a-zÀ-ÖØ-öø-˿Ͱ-ͽͿ-῿‌-‍⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�][-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['Name']


class XSDSimpleTypeNCName(XSDSimpleTypeName):
    """
    
        
Pattern: [A-Z_a-zÀ-ÖØ-öø-˿Ͱ-ͽͿ-῿‌-‍⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�][-.0-9A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['NCName']


class XSDSimpleTypeID(XSDSimpleTypeNCName):
    """"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['ID']


class XSDSimpleTypeIDREF(XSDSimpleTypeNCName):
    """"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['IDREF']


class XSDSimpleTypeLanguage(XSDSimpleTypeToken):
    """
    
        
Pattern: ([a-zA-Z]{2}|[iI]-[a-zA-Z]+|[xX]-[a-zA-Z]{1,8})(-[a-zA-Z]{1,8})*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['language']


class XSDSimpleTypeAboveBelow(XSDSimpleTypeToken):
    """The above-below type is used to indicate whether one element appears above or below another element.
    
    Permitted Values: ``'above'``, ``'below'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['above-below']


class XSDSimpleTypeBeamLevel(XSDSimpleTypePositiveInteger):
    """The MusicXML format supports six levels of beaming, up to 1024th notes. Unlike the number-level type, the beam-level type identifies concurrent beams in a beam group. It does not distinguish overlapping beams such as grace notes within regular notes, or beams used in different voices."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['beam-level']


class XSDSimpleTypeColor(XSDSimpleTypeToken):
    """The color type indicates the color of an element. Color may be represented as hexadecimal RGB triples, as in HTML, or as hexadecimal ARGB tuples, with the A indicating alpha of transparency. An alpha value of 00 is totally transparent; FF is totally opaque. If RGB is used, the A value is assumed to be FF.

For instance, the RGB value "#800080" represents purple. An ARGB value of "#40800080" would be a transparent purple.

As in SVG 1.1, colors are defined in terms of the sRGB color space (IEC 61966).
    
        
Pattern: #[\dA-F]{6}([\dA-F][\dA-F])?
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['color']


class XSDSimpleTypeCommaSeparatedText(XSDSimpleTypeToken):
    """The comma-separated-text type is used to specify a comma-separated list of text elements, as is used by the font-family attribute.
    
        
Pattern: [^,]+(, ?[^,]+)*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['comma-separated-text']


class XSDSimpleTypeCssFontSize(XSDSimpleTypeToken):
    """The css-font-size type includes the CSS font sizes used as an alternative to a numeric point size.
    
    Permitted Values: ``'xx-small'``, ``'x-small'``, ``'small'``, ``'medium'``, ``'large'``, ``'x-large'``, ``'xx-large'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['css-font-size']


class XSDSimpleTypeDivisions(XSDSimpleTypeDecimal):
    """The divisions type is used to express values in terms of the musical divisions defined by the divisions element. It is preferred that these be integer values both for MIDI interoperability and to avoid roundoff errors."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['divisions']


class XSDSimpleTypeEnclosureShape(XSDSimpleTypeToken):
    """The enclosure-shape type describes the shape and presence / absence of an enclosure around text or symbols. A bracket enclosure is similar to a rectangle with the bottom line missing, as is common in jazz notation. An inverted-bracket enclosure is similar to a rectangle with the top line missing.
    
    Permitted Values: ``'rectangle'``, ``'square'``, ``'oval'``, ``'circle'``, ``'bracket'``, ``'inverted-bracket'``, ``'triangle'``, ``'diamond'``, ``'pentagon'``, ``'hexagon'``, ``'heptagon'``, ``'octagon'``, ``'nonagon'``, ``'decagon'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['enclosure-shape']


class XSDSimpleTypeFermataShape(XSDSimpleTypeString):
    """The fermata-shape type represents the shape of the fermata sign. The empty value is equivalent to the normal value.
    
    Permitted Values: ``'normal'``, ``'angled'``, ``'square'``, ``'double-angled'``, ``'double-square'``, ``'double-dot'``, ``'half-curve'``, ``'curlew'``, ``''``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['fermata-shape']


class XSDSimpleTypeFontFamily(XSDSimpleTypeCommaSeparatedText):
    """The font-family is a comma-separated list of font names. These can be specific font styles such as Maestro or Opus, or one of several generic font styles: music, engraved, handwritten, text, serif, sans-serif, handwritten, cursive, fantasy, and monospace. The music, engraved, and handwritten values refer to music fonts; the rest refer to text fonts. The fantasy style refers to decorative text such as found in older German-style printing."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['font-family']


class XSDSimpleTypeFontStyle(XSDSimpleTypeToken):
    """The font-style type represents a simplified version of the CSS font-style property.
    
    Permitted Values: ``'normal'``, ``'italic'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['font-style']


class XSDSimpleTypeFontWeight(XSDSimpleTypeToken):
    """The font-weight type represents a simplified version of the CSS font-weight property.
    
    Permitted Values: ``'normal'``, ``'bold'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['font-weight']


class XSDSimpleTypeLeftCenterRight(XSDSimpleTypeToken):
    """The left-center-right type is used to define horizontal alignment and text justification.
    
    Permitted Values: ``'left'``, ``'center'``, ``'right'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['left-center-right']


class XSDSimpleTypeLeftRight(XSDSimpleTypeToken):
    """The left-right type is used to indicate whether one element appears to the left or the right of another element.
    
    Permitted Values: ``'left'``, ``'right'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['left-right']


class XSDSimpleTypeLineLength(XSDSimpleTypeToken):
    """The line-length type distinguishes between different line lengths for doit, falloff, plop, and scoop articulations.
    
    Permitted Values: ``'short'``, ``'medium'``, ``'long'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['line-length']


class XSDSimpleTypeLineShape(XSDSimpleTypeToken):
    """The line-shape type distinguishes between straight and curved lines.
    
    Permitted Values: ``'straight'``, ``'curved'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['line-shape']


class XSDSimpleTypeLineType(XSDSimpleTypeToken):
    """The line-type type distinguishes between solid, dashed, dotted, and wavy lines.
    
    Permitted Values: ``'solid'``, ``'dashed'``, ``'dotted'``, ``'wavy'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['line-type']


class XSDSimpleTypeMidi16(XSDSimpleTypePositiveInteger):
    """The midi-16 type is used to express MIDI 1.0 values that range from 1 to 16."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['midi-16']


class XSDSimpleTypeMidi128(XSDSimpleTypePositiveInteger):
    """The midi-128 type is used to express MIDI 1.0 values that range from 1 to 128."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['midi-128']


class XSDSimpleTypeMidi16384(XSDSimpleTypePositiveInteger):
    """The midi-16384 type is used to express MIDI 1.0 values that range from 1 to 16,384."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['midi-16384']


class XSDSimpleTypeMute(XSDSimpleTypeString):
    """The mute type represents muting for different instruments, including brass, winds, and strings. The on and off values are used for undifferentiated mutes. The remaining values represent specific mutes.
    
    Permitted Values: ``'on'``, ``'off'``, ``'straight'``, ``'cup'``, ``'harmon-no-stem'``, ``'harmon-stem'``, ``'bucket'``, ``'plunger'``, ``'hat'``, ``'solotone'``, ``'practice'``, ``'stop-mute'``, ``'stop-hand'``, ``'echo'``, ``'palm'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['mute']


class XSDSimpleTypeNonNegativeDecimal(XSDSimpleTypeDecimal):
    """The non-negative-decimal type specifies a non-negative decimal value."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['non-negative-decimal']


class XSDSimpleTypeNumberLevel(XSDSimpleTypePositiveInteger):
    """Slurs, tuplets, and many other features can be concurrent and overlap within a single musical part. The number-level entity distinguishes up to 16 concurrent objects of the same type when the objects overlap in MusicXML document order. Values greater than 6 are usually only needed for music with a large number of divisi staves in a single part, or if there are more than 6 cross-staff arpeggios in a single measure. When a number-level value is implied, the value is 1 by default.

When polyphonic parts are involved, the ordering within a MusicXML document can differ from musical score order. As an example, say we have a piano part in 4/4 where within a single measure, all the notes on the top staff are followed by all the notes on the bottom staff. In this example, each staff has a slur that starts on beat 2 and stops on beat 3, and there is a third slur that goes from beat 1 of one staff to beat 4 of the other staff.

In this situation, the two mid-measure slurs can use the same number because they do not overlap in MusicXML document order, even though they do overlap in musical score order. Within the MusicXML document, the top staff slur will both start and stop before the bottom staff slur starts and stops.

If the cross-staff slur starts in the top staff and stops in the bottom staff, it will need a separate number from the mid-measure slurs because it overlaps those slurs in MusicXML document order. However, if the cross-staff slur starts in the bottom staff and stops in the top staff, all three slurs can use the same number. None of them overlap within the MusicXML document, even though they all overlap each other in the musical score order. Within the MusicXML document, the start and stop of the top-staff slur will be followed by the stop and start of the cross-staff slur, followed by the start and stop of the bottom-staff slur.

As this example demonstrates, a reading program should be prepared to handle cases where the number-levels start and stop in an arbitrary order. Because the start and stop values refer to musical score order, a program may find the stopping point of an object earlier in the MusicXML document than it will find its starting point."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['number-level']


class XSDSimpleTypeNumberOfLines(XSDSimpleTypeNonNegativeInteger):
    """The number-of-lines type is used to specify the number of lines in text decoration attributes."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['number-of-lines']


class XSDSimpleTypeNumeralValue(XSDSimpleTypePositiveInteger):
    """The numeral-value type represents a Roman numeral or Nashville number value as a positive integer from 1 to 7."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['numeral-value']


class XSDSimpleTypeOverUnder(XSDSimpleTypeToken):
    """The over-under type is used to indicate whether the tips of curved lines such as slurs and ties are overhand (tips down) or underhand (tips up).
    
    Permitted Values: ``'over'``, ``'under'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['over-under']


class XSDSimpleTypePercent(XSDSimpleTypeDecimal):
    """The percent type specifies a percentage from 0 to 100."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['percent']


class XSDSimpleTypePositiveDecimal(XSDSimpleTypeDecimal):
    """The positive-decimal type specifies a positive decimal value."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['positive-decimal']


class XSDSimpleTypePositiveDivisions(XSDSimpleTypeDivisions):
    """The positive-divisions type restricts divisions values to positive numbers."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['positive-divisions']


class XSDSimpleTypeRotationDegrees(XSDSimpleTypeDecimal):
    """The rotation-degrees type specifies rotation, pan, and elevation values in degrees. Values range from -180 to 180."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['rotation-degrees']


class XSDSimpleTypeSemiPitched(XSDSimpleTypeString):
    """The semi-pitched type represents categories of indefinite pitch for percussion instruments.
    
    Permitted Values: ``'high'``, ``'medium-high'``, ``'medium'``, ``'medium-low'``, ``'low'``, ``'very-low'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['semi-pitched']


class XSDSimpleTypeSmuflGlyphName(XSDSimpleTypeNMTOKEN):
    """The smufl-glyph-name type is used for attributes that reference a specific Standard Music Font Layout (SMuFL) character. The value is a SMuFL canonical glyph name, not a code point. For instance, the value for a standard piano pedal mark would be keyboardPedalPed, not U+E650."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-glyph-name']


class XSDSimpleTypeSmuflAccidentalGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-accidental-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) accidental character. The value is a SMuFL canonical glyph name that starts with one of the strings used at the start of glyph names for SMuFL accidentals.
    
        
Pattern: (acc|medRenFla|medRenNatura|medRenShar|kievanAccidental)([-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]+)
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-accidental-glyph-name']


class XSDSimpleTypeSmuflCodaGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-coda-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) coda character. The value is a SMuFL canonical glyph name that starts with coda.
    
        
Pattern: coda[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-coda-glyph-name']


class XSDSimpleTypeSmuflLyricsGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-lyrics-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) lyrics elision character. The value is a SMuFL canonical glyph name that starts with lyrics.
    
        
Pattern: lyrics[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]+
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-lyrics-glyph-name']


class XSDSimpleTypeSmuflPictogramGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-pictogram-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) percussion pictogram character. The value is a SMuFL canonical glyph name that starts with pict.
    
        
Pattern: pict[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]+
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-pictogram-glyph-name']


class XSDSimpleTypeSmuflSegnoGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-segno-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) segno character. The value is a SMuFL canonical glyph name that starts with segno.
    
        
Pattern: segno[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-segno-glyph-name']


class XSDSimpleTypeSmuflWavyLineGlyphName(XSDSimpleTypeSmuflGlyphName):
    """The smufl-wavy-line-glyph-name type is used to reference a specific Standard Music Font Layout (SMuFL) wavy line character. The value is a SMuFL canonical glyph name that either starts with wiggle, or begins with guitar and ends with VibratoStroke. This includes all the glyphs in the Multi-segment lines range, excluding the beam glyphs.
    
        
Pattern: (wiggle[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]+)|(guitar[-.0-9:A-Z_a-z·À-ÖØ-öø-ͽͿ-῿‌-‍‿⁀⁰-↏Ⰰ-⿯、-퟿豈-﷏ﷰ-�]*VibratoStroke)
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['smufl-wavy-line-glyph-name']


class XSDSimpleTypeStartNote(XSDSimpleTypeToken):
    """The start-note type describes the starting note of trills and mordents for playback, relative to the current note.
    
    Permitted Values: ``'upper'``, ``'main'``, ``'below'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-note']


class XSDSimpleTypeStartStop(XSDSimpleTypeToken):
    """The start-stop type is used for an attribute of musical elements that can either start or stop, such as tuplets.

The values of start and stop refer to how an element appears in musical score order, not in MusicXML document order. An element with a stop attribute may precede the corresponding element with a start attribute within a MusicXML document. This is particularly common in multi-staff music. For example, the stopping point for a tuplet may appear in staff 1 before the starting point for the tuplet appears in staff 2 later in the document.

When multiple elements with the same tag are used within the same note, their order within the MusicXML document should match the musical score order.
    
    Permitted Values: ``'start'``, ``'stop'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-stop']


class XSDSimpleTypeStartStopContinue(XSDSimpleTypeToken):
    """The start-stop-continue type is used for an attribute of musical elements that can either start or stop, but also need to refer to an intermediate point in the symbol, as for complex slurs or for formatting of symbols across system breaks.

The values of start, stop, and continue refer to how an element appears in musical score order, not in MusicXML document order. An element with a stop attribute may precede the corresponding element with a start attribute within a MusicXML document. This is particularly common in multi-staff music. For example, the stopping point for a slur may appear in staff 1 before the starting point for the slur appears in staff 2 later in the document.

When multiple elements with the same tag are used within the same note, their order within the MusicXML document should match the musical score order. For example, a note that marks both the end of one slur and the start of a new slur should have the incoming slur element with a type of stop precede the outgoing slur element with a type of start.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'continue'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-stop-continue']


class XSDSimpleTypeStartStopSingle(XSDSimpleTypeToken):
    """The start-stop-single type is used for an attribute of musical elements that can be used for either multi-note or single-note musical elements, as for groupings.

When multiple elements with the same tag are used within the same note, their order within the MusicXML document should match the musical score order.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'single'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-stop-single']


class XSDSimpleTypeStringNumber(XSDSimpleTypePositiveInteger):
    """The string-number type indicates a string number. Strings are numbered from high to low, with 1 being the highest pitched full-length string."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['string-number']


class XSDSimpleTypeSymbolSize(XSDSimpleTypeToken):
    """The symbol-size type is used to distinguish between full, cue sized, grace cue sized, and oversized symbols.
    
    Permitted Values: ``'full'``, ``'cue'``, ``'grace-cue'``, ``'large'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['symbol-size']


class XSDSimpleTypeTenths(XSDSimpleTypeDecimal):
    """The tenths type is a number representing tenths of interline staff space (positive or negative). Both integer and decimal values are allowed, such as 5 for a half space and 2.5 for a quarter space. Interline space is measured from the middle of a staff line.

Distances in a MusicXML file are measured in tenths of staff space. Tenths are then scaled to millimeters within the scaling element, used in the defaults element at the start of a score. Individual staves can apply a scaling factor to adjust staff size. When a MusicXML element or attribute refers to tenths, it means the global tenths defined by the scaling element, not the local tenths as adjusted by the staff-size element."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tenths']


class XSDSimpleTypeTextDirection(XSDSimpleTypeToken):
    """The text-direction type is used to adjust and override the Unicode bidirectional text algorithm, similar to the Directionality data category in the W3C Internationalization Tag Set recommendation. Values are ltr (left-to-right embed), rtl (right-to-left embed), lro (left-to-right bidi-override), and rlo (right-to-left bidi-override). The default value is ltr. This type is typically used by applications that store text in left-to-right visual order rather than logical order. Such applications can use the lro value to better communicate with other applications that more fully support bidirectional text.
    
    Permitted Values: ``'ltr'``, ``'rtl'``, ``'lro'``, ``'rlo'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['text-direction']


class XSDSimpleTypeTiedType(XSDSimpleTypeToken):
    """The tied-type type is used as an attribute of the tied element to specify where the visual representation of a tie begins and ends. A tied element which joins two notes of the same pitch can be specified with tied-type start on the first note and tied-type stop on the second note. To indicate a note should be undamped, use a single tied element with tied-type let-ring. For other ties that are visually attached to a single note, such as a tie leading into or out of a repeated section or coda, use two tied elements on the same note, one start and one stop.

In start-stop cases, ties can add more elements using a continue type. This is typically used to specify the formatting of cross-system ties.

When multiple elements with the same tag are used within the same note, their order within the MusicXML document should match the musical score order. For example, a note with a tie at the end of a first ending should have the tied element with a type of start precede the tied element with a type of stop.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'continue'``, ``'let-ring'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tied-type']


class XSDSimpleTypeTimeOnly(XSDSimpleTypeToken):
    """The time-only type is used to indicate that a particular playback- or listening-related element only applies particular times through a repeated section. The value is a comma-separated list of positive integers arranged in ascending order, indicating which times through the repeated section that the element applies.
    
        
Pattern: [1-9][0-9]*(, ?[1-9][0-9]*)*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['time-only']


class XSDSimpleTypeTopBottom(XSDSimpleTypeToken):
    """The top-bottom type is used to indicate the top or bottom part of a vertical shape like non-arpeggiate.
    
    Permitted Values: ``'top'``, ``'bottom'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['top-bottom']


class XSDSimpleTypeTremoloType(XSDSimpleTypeToken):
    """The tremolo-type is used to distinguish double-note, single-note, and unmeasured tremolos.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'single'``, ``'unmeasured'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tremolo-type']


class XSDSimpleTypeTrillBeats(XSDSimpleTypeDecimal):
    """The trill-beats type specifies the beats used in a trill-sound or bend-sound attribute group. It is a decimal value with a minimum value of 2."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['trill-beats']


class XSDSimpleTypeTrillStep(XSDSimpleTypeToken):
    """The trill-step type describes the alternating note of trills and mordents for playback, relative to the current note.
    
    Permitted Values: ``'whole'``, ``'half'``, ``'unison'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['trill-step']


class XSDSimpleTypeTwoNoteTurn(XSDSimpleTypeToken):
    """The two-note-turn type describes the ending notes of trills and mordents for playback, relative to the current note.
    
    Permitted Values: ``'whole'``, ``'half'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['two-note-turn']


class XSDSimpleTypeUpDown(XSDSimpleTypeToken):
    """The up-down type is used for the direction of arrows and other pointed symbols like vertical accents, indicating which way the tip is pointing.
    
    Permitted Values: ``'up'``, ``'down'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['up-down']


class XSDSimpleTypeUprightInverted(XSDSimpleTypeToken):
    """The upright-inverted type describes the appearance of a fermata element. The value is upright if not specified.
    
    Permitted Values: ``'upright'``, ``'inverted'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['upright-inverted']


class XSDSimpleTypeValign(XSDSimpleTypeToken):
    """The valign type is used to indicate vertical alignment to the top, middle, bottom, or baseline of the text. If the text is on multiple lines, baseline alignment refers to the baseline of the lowest line of text. Defaults are implementation-dependent.
    
    Permitted Values: ``'top'``, ``'middle'``, ``'bottom'``, ``'baseline'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['valign']


class XSDSimpleTypeValignImage(XSDSimpleTypeToken):
    """The valign-image type is used to indicate vertical alignment for images and graphics, so it does not include a baseline value. Defaults are implementation-dependent.
    
    Permitted Values: ``'top'``, ``'middle'``, ``'bottom'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['valign-image']


class XSDSimpleTypeYesNo(XSDSimpleTypeToken):
    """The yes-no type is used for boolean-like attributes. We cannot use W3C XML Schema booleans due to their restrictions on expression of boolean values.
    
    Permitted Values: ``'yes'``, ``'no'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['yes-no']


class XSDSimpleTypeYyyyMmDd(XSDSimpleTypeDate):
    """Calendar dates are represented yyyy-mm-dd format, following ISO 8601. This is a W3C XML Schema date type, but without the optional timezone data.
    
        
Pattern: [^:Z]*
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['yyyy-mm-dd']


class XSDSimpleTypeCancelLocation(XSDSimpleTypeString):
    """The cancel-location type is used to indicate where a key signature cancellation appears relative to a new key signature: to the left, to the right, or before the barline and to the left. It is left by default. For mid-measure key elements, a cancel-location of before-barline should be treated like a cancel-location of left.
    
    Permitted Values: ``'left'``, ``'right'``, ``'before-barline'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['cancel-location']


class XSDSimpleTypeClefSign(XSDSimpleTypeString):
    """The clef-sign type represents the different clef symbols. The jianpu sign indicates that the music that follows should be in jianpu numbered notation, just as the TAB sign indicates that the music that follows should be in tablature notation. Unlike TAB, a jianpu sign does not correspond to a visual clef notation.

The none sign is deprecated as of MusicXML 4.0. Use the clef element's print-object attribute instead. When the none sign is used, notes should be displayed as if in treble clef.
    
    Permitted Values: ``'G'``, ``'F'``, ``'C'``, ``'percussion'``, ``'TAB'``, ``'jianpu'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['clef-sign']


class XSDSimpleTypeFifths(XSDSimpleTypeInteger):
    """The fifths type represents the number of flats or sharps in a traditional key signature. Negative numbers are used for flats and positive numbers for sharps, reflecting the key's placement within the circle of fifths (hence the type name)."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['fifths']


class XSDSimpleTypeMode(XSDSimpleTypeString):
    """The mode type is used to specify major/minor and other mode distinctions. Valid mode values include major, minor, dorian, phrygian, lydian, mixolydian, aeolian, ionian, locrian, and none."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['mode']


class XSDSimpleTypeShowFrets(XSDSimpleTypeToken):
    """The show-frets type indicates whether to show tablature frets as numbers (0, 1, 2) or letters (a, b, c). The default choice is numbers.
    
    Permitted Values: ``'numbers'``, ``'letters'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['show-frets']


class XSDSimpleTypeStaffLine(XSDSimpleTypePositiveInteger):
    """The staff-line type indicates the line on a given staff. Staff lines are numbered from bottom to top, with 1 being the bottom line on a staff."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['staff-line']


class XSDSimpleTypeStaffLinePosition(XSDSimpleTypeInteger):
    """The staff-line-position type indicates the line position on a given staff. Staff lines are numbered from bottom to top, with 1 being the bottom line on a staff. A staff-line-position value can extend beyond the range of the lines on the current staff."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['staff-line-position']


class XSDSimpleTypeStaffNumber(XSDSimpleTypePositiveInteger):
    """The staff-number type indicates staff numbers within a multi-staff part. Staves are numbered from top to bottom, with 1 being the top staff on a part."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['staff-number']


class XSDSimpleTypeStaffType(XSDSimpleTypeString):
    """The staff-type value can be ossia, editorial, cue, alternate, or regular. An ossia staff represents music that can be played instead of what appears on the regular staff. An editorial staff also represents musical alternatives, but is created by an editor rather than the composer. It can be used for suggested interpretations or alternatives from other sources. A cue staff represents music from another part. An alternate staff shares the same music as the prior staff, but displayed differently (e.g., treble and bass clef, standard notation and tablature). It is not included in playback. An alternate staff provides more information to an application reading a file than encoding the same music in separate parts, so its use is preferred in this situation if feasible. A regular staff is the standard default staff-type.
    
    Permitted Values: ``'ossia'``, ``'editorial'``, ``'cue'``, ``'alternate'``, ``'regular'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['staff-type']


class XSDSimpleTypeTimeRelation(XSDSimpleTypeString):
    """The time-relation type indicates the symbol used to represent the interchangeable aspect of dual time signatures.
    
    Permitted Values: ``'parentheses'``, ``'bracket'``, ``'equals'``, ``'slash'``, ``'space'``, ``'hyphen'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['time-relation']


class XSDSimpleTypeTimeSeparator(XSDSimpleTypeToken):
    """The time-separator type indicates how to display the arrangement between the beats and beat-type values in a time signature. The default value is none. The horizontal, diagonal, and vertical values represent horizontal, diagonal lower-left to upper-right, and vertical lines respectively. For these values, the beats and beat-type values are arranged on either side of the separator line. The none value represents no separator with the beats and beat-type arranged vertically. The adjacent value represents no separator with the beats and beat-type arranged horizontally.
    
    Permitted Values: ``'none'``, ``'horizontal'``, ``'diagonal'``, ``'vertical'``, ``'adjacent'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['time-separator']


class XSDSimpleTypeTimeSymbol(XSDSimpleTypeToken):
    """The time-symbol type indicates how to display a time signature. The normal value is the usual fractional display, and is the implied symbol type if none is specified. Other options are the common and cut time symbols, as well as a single number with an implied denominator. The note symbol indicates that the beat-type should be represented with the corresponding downstem note rather than a number. The dotted-note symbol indicates that the beat-type should be represented with a dotted downstem note that corresponds to three times the beat-type value, and a numerator that is one third the beats value.
    
    Permitted Values: ``'common'``, ``'cut'``, ``'single-number'``, ``'note'``, ``'dotted-note'``, ``'normal'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['time-symbol']


class XSDSimpleTypeBackwardForward(XSDSimpleTypeToken):
    """The backward-forward type is used to specify repeat directions. The start of the repeat has a forward direction while the end of the repeat has a backward direction.
    
    Permitted Values: ``'backward'``, ``'forward'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['backward-forward']


class XSDSimpleTypeBarStyle(XSDSimpleTypeString):
    """The bar-style type represents barline style information. Choices are regular, dotted, dashed, heavy, light-light, light-heavy, heavy-light, heavy-heavy, tick (a short stroke through the top line), short (a partial barline between the 2nd and 4th lines), and none.
    
    Permitted Values: ``'regular'``, ``'dotted'``, ``'dashed'``, ``'heavy'``, ``'light-light'``, ``'light-heavy'``, ``'heavy-light'``, ``'heavy-heavy'``, ``'tick'``, ``'short'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['bar-style']


class XSDSimpleTypeEndingNumber(XSDSimpleTypeToken):
    """The ending-number type is used to specify either a comma-separated list of positive integers without leading zeros, or a string of zero or more spaces. It is used for the number attribute of the ending element. The zero or more spaces version is used when software knows that an ending is present, but cannot determine the type of the ending.
    
        
Pattern: ([ ]*)|([1-9][0-9]*(, ?[1-9][0-9]*)*)
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['ending-number']


class XSDSimpleTypeRightLeftMiddle(XSDSimpleTypeToken):
    """The right-left-middle type is used to specify barline location.
    
    Permitted Values: ``'right'``, ``'left'``, ``'middle'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['right-left-middle']


class XSDSimpleTypeStartStopDiscontinue(XSDSimpleTypeToken):
    """The start-stop-discontinue type is used to specify ending types. Typically, the start type is associated with the left barline of the first measure in an ending. The stop and discontinue types are associated with the right barline of the last measure in an ending. Stop is used when the ending mark concludes with a downward jog, as is typical for first endings. Discontinue is used when there is no downward jog, as is typical for second endings that do not conclude a piece.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'discontinue'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-stop-discontinue']


class XSDSimpleTypeWinged(XSDSimpleTypeToken):
    """The winged attribute indicates whether the repeat has winged extensions that appear above and below the barline. The straight and curved values represent single wings, while the double-straight and double-curved values represent double wings. The none value indicates no wings and is the default.
    
    Permitted Values: ``'none'``, ``'straight'``, ``'curved'``, ``'double-straight'``, ``'double-curved'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['winged']


class XSDSimpleTypeAccordionMiddle(XSDSimpleTypePositiveInteger):
    """The accordion-middle type may have values of 1, 2, or 3, corresponding to having 1 to 3 dots in the middle section of the accordion registration symbol. This type is not used if no dots are present."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['accordion-middle']


class XSDSimpleTypeBeaterValue(XSDSimpleTypeString):
    """The beater-value type represents pictograms for beaters, mallets, and sticks that do not have different materials represented in the pictogram. The finger and hammer values are in addition to Stone's list.
    
    Permitted Values: ``'bow'``, ``'chime hammer'``, ``'coin'``, ``'drum stick'``, ``'finger'``, ``'fingernail'``, ``'fist'``, ``'guiro scraper'``, ``'hammer'``, ``'hand'``, ``'jazz stick'``, ``'knitting needle'``, ``'metal hammer'``, ``'slide brush on gong'``, ``'snare stick'``, ``'spoon mallet'``, ``'superball'``, ``'triangle beater'``, ``'triangle beater plain'``, ``'wire brush'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['beater-value']


class XSDSimpleTypeDegreeSymbolValue(XSDSimpleTypeToken):
    """The degree-symbol-value type indicates which symbol should be used in specifying a degree.
    
    Permitted Values: ``'major'``, ``'minor'``, ``'augmented'``, ``'diminished'``, ``'half-diminished'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['degree-symbol-value']


class XSDSimpleTypeDegreeTypeValue(XSDSimpleTypeString):
    """The degree-type-value type indicates whether the current degree element is an addition, alteration, or subtraction to the kind of the current chord in the harmony element.
    
    Permitted Values: ``'add'``, ``'alter'``, ``'subtract'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['degree-type-value']


class XSDSimpleTypeEffectValue(XSDSimpleTypeString):
    """The effect-value type represents pictograms for sound effect percussion instruments. The cannon, lotus flute, and megaphone values are in addition to Stone's list.
    
    Permitted Values: ``'anvil'``, ``'auto horn'``, ``'bird whistle'``, ``'cannon'``, ``'duck call'``, ``'gun shot'``, ``'klaxon horn'``, ``'lions roar'``, ``'lotus flute'``, ``'megaphone'``, ``'police whistle'``, ``'siren'``, ``'slide whistle'``, ``'thunder sheet'``, ``'wind machine'``, ``'wind whistle'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['effect-value']


class XSDSimpleTypeGlassValue(XSDSimpleTypeString):
    """The glass-value type represents pictograms for glass percussion instruments.
    
    Permitted Values: ``'glass harmonica'``, ``'glass harp'``, ``'wind chimes'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['glass-value']


class XSDSimpleTypeHarmonyArrangement(XSDSimpleTypeToken):
    """The harmony-arrangement type indicates how stacked chords and bass notes are displayed within a harmony element. The vertical value specifies that the second element appears below the first. The horizontal value specifies that the second element appears to the right of the first. The diagonal value specifies that the second element appears both below and to the right of the first.
    
    Permitted Values: ``'vertical'``, ``'horizontal'``, ``'diagonal'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['harmony-arrangement']


class XSDSimpleTypeHarmonyType(XSDSimpleTypeToken):
    """The harmony-type type differentiates different types of harmonies when alternate harmonies are possible. Explicit harmonies have all note present in the music; implied have some notes missing but implied; alternate represents alternate analyses.
    
    Permitted Values: ``'explicit'``, ``'implied'``, ``'alternate'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['harmony-type']


class XSDSimpleTypeKindValue(XSDSimpleTypeString):
    """A kind-value indicates the type of chord. Degree elements can then add, subtract, or alter from these starting points. Values include:

Triads:
    major (major third, perfect fifth)
    minor (minor third, perfect fifth)
    augmented (major third, augmented fifth)
    diminished (minor third, diminished fifth)
Sevenths:
    dominant (major triad, minor seventh)
    major-seventh (major triad, major seventh)
    minor-seventh (minor triad, minor seventh)
    diminished-seventh (diminished triad, diminished seventh)
    augmented-seventh (augmented triad, minor seventh)
    half-diminished (diminished triad, minor seventh)
    major-minor (minor triad, major seventh)
Sixths:
    major-sixth (major triad, added sixth)
    minor-sixth (minor triad, added sixth)
Ninths:
    dominant-ninth (dominant-seventh, major ninth)
    major-ninth (major-seventh, major ninth)
    minor-ninth (minor-seventh, major ninth)
11ths (usually as the basis for alteration):
    dominant-11th (dominant-ninth, perfect 11th)
    major-11th (major-ninth, perfect 11th)
    minor-11th (minor-ninth, perfect 11th)
13ths (usually as the basis for alteration):
    dominant-13th (dominant-11th, major 13th)
    major-13th (major-11th, major 13th)
    minor-13th (minor-11th, major 13th)
Suspended:
    suspended-second (major second, perfect fifth)
    suspended-fourth (perfect fourth, perfect fifth)
Functional sixths:
    Neapolitan
    Italian
    French
    German
Other:
    pedal (pedal-point bass)
    power (perfect fifth)
    Tristan

The "other" kind is used when the harmony is entirely composed of add elements.

The "none" kind is used to explicitly encode absence of chords or functional harmony. In this case, the root, numeral, or function element has no meaning. When using the root or numeral element, the root-step or numeral-step text attribute should be set to the empty string to keep the root or numeral from being displayed.
    
    Permitted Values: ``'major'``, ``'minor'``, ``'augmented'``, ``'diminished'``, ``'dominant'``, ``'major-seventh'``, ``'minor-seventh'``, ``'diminished-seventh'``, ``'augmented-seventh'``, ``'half-diminished'``, ``'major-minor'``, ``'major-sixth'``, ``'minor-sixth'``, ``'dominant-ninth'``, ``'major-ninth'``, ``'minor-ninth'``, ``'dominant-11th'``, ``'major-11th'``, ``'minor-11th'``, ``'dominant-13th'``, ``'major-13th'``, ``'minor-13th'``, ``'suspended-second'``, ``'suspended-fourth'``, ``'Neapolitan'``, ``'Italian'``, ``'French'``, ``'German'``, ``'pedal'``, ``'power'``, ``'Tristan'``, ``'other'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['kind-value']


class XSDSimpleTypeLineEnd(XSDSimpleTypeToken):
    """The line-end type specifies if there is a jog up or down (or both), an arrow, or nothing at the start or end of a bracket.
    
    Permitted Values: ``'up'``, ``'down'``, ``'both'``, ``'arrow'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['line-end']


class XSDSimpleTypeMeasureNumberingValue(XSDSimpleTypeToken):
    """The measure-numbering-value type describes how measure numbers are displayed on this part: no numbers, numbers every measure, or numbers every system.
    
    Permitted Values: ``'none'``, ``'measure'``, ``'system'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['measure-numbering-value']


class XSDSimpleTypeMembraneValue(XSDSimpleTypeString):
    """The membrane-value type represents pictograms for membrane percussion instruments.
    
    Permitted Values: ``'bass drum'``, ``'bass drum on side'``, ``'bongos'``, ``'Chinese tomtom'``, ``'conga drum'``, ``'cuica'``, ``'goblet drum'``, ``'Indo-American tomtom'``, ``'Japanese tomtom'``, ``'military drum'``, ``'snare drum'``, ``'snare drum snares off'``, ``'tabla'``, ``'tambourine'``, ``'tenor drum'``, ``'timbales'``, ``'tomtom'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['membrane-value']


class XSDSimpleTypeMetalValue(XSDSimpleTypeString):
    """The metal-value type represents pictograms for metal percussion instruments. The hi-hat value refers to a pictogram like Stone's high-hat cymbals but without the long vertical line at the bottom.
    
    Permitted Values: ``'agogo'``, ``'almglocken'``, ``'bell'``, ``'bell plate'``, ``'bell tree'``, ``'brake drum'``, ``'cencerro'``, ``'chain rattle'``, ``'Chinese cymbal'``, ``'cowbell'``, ``'crash cymbals'``, ``'crotale'``, ``'cymbal tongs'``, ``'domed gong'``, ``'finger cymbals'``, ``'flexatone'``, ``'gong'``, ``'hi-hat'``, ``'high-hat cymbals'``, ``'handbell'``, ``'jaw harp'``, ``'jingle bells'``, ``'musical saw'``, ``'shell bells'``, ``'sistrum'``, ``'sizzle cymbal'``, ``'sleigh bells'``, ``'suspended cymbal'``, ``'tam tam'``, ``'tam tam with beater'``, ``'triangle'``, ``'Vietnamese hat'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['metal-value']


class XSDSimpleTypeMilliseconds(XSDSimpleTypeNonNegativeInteger):
    """The milliseconds type represents an integral number of milliseconds."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['milliseconds']


class XSDSimpleTypeNumeralMode(XSDSimpleTypeString):
    """The numeral-mode type specifies the mode similar to the mode type, but with a restricted set of values. The different minor values are used to interpret numeral-root values of 6 and 7 when present in a minor key. The harmonic minor value sharpens the 7 and the melodic minor value sharpens both 6 and 7. If a minor mode is used without qualification, either in the mode or numeral-mode elements, natural minor is used.
    
    Permitted Values: ``'major'``, ``'minor'``, ``'natural minor'``, ``'melodic minor'``, ``'harmonic minor'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['numeral-mode']


class XSDSimpleTypeOnOff(XSDSimpleTypeToken):
    """The on-off type is used for notation elements such as string mutes.
    
    Permitted Values: ``'on'``, ``'off'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['on-off']


class XSDSimpleTypePedalType(XSDSimpleTypeToken):
    """The pedal-type simple type is used to distinguish types of pedal directions. The start value indicates the start of a damper pedal, while the sostenuto value indicates the start of a sostenuto pedal. The other values can be used with either the damper or sostenuto pedal. The soft pedal is not included here because there is no special symbol or graphic used for it beyond what can be specified with words and bracket elements.

The change, continue, discontinue, and resume types are used when the line attribute is yes. The change type indicates a pedal lift and retake indicated with an inverted V marking. The continue type allows more precise formatting across system breaks and for more complex pedaling lines. The discontinue type indicates the end of a pedal line that does not include the explicit lift represented by the stop type. The resume type indicates the start of a pedal line that does not include the downstroke represented by the start type. It can be used when a line resumes after being discontinued, or to start a pedal line that is preceded by a text or symbol representation of the pedal.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'sostenuto'``, ``'change'``, ``'continue'``, ``'discontinue'``, ``'resume'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['pedal-type']


class XSDSimpleTypePitchedValue(XSDSimpleTypeString):
    """The pitched-value type represents pictograms for pitched percussion instruments. The chimes and tubular chimes values distinguish the single-line and double-line versions of the pictogram.
    
    Permitted Values: ``'celesta'``, ``'chimes'``, ``'glockenspiel'``, ``'lithophone'``, ``'mallet'``, ``'marimba'``, ``'steel drums'``, ``'tubaphone'``, ``'tubular chimes'``, ``'vibraphone'``, ``'xylophone'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['pitched-value']


class XSDSimpleTypePrincipalVoiceSymbol(XSDSimpleTypeString):
    """The principal-voice-symbol type represents the type of symbol used to indicate a principal or secondary voice. The "plain" value represents a plain square bracket. The value of "none" is used for analysis markup when the principal-voice element does not have a corresponding appearance in the score.
    
    Permitted Values: ``'Hauptstimme'``, ``'Nebenstimme'``, ``'plain'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['principal-voice-symbol']


class XSDSimpleTypeStaffDivideSymbol(XSDSimpleTypeToken):
    """The staff-divide-symbol type is used for staff division symbols. The down, up, and up-down values correspond to SMuFL code points U+E00B, U+E00C, and U+E00D respectively.
    
    Permitted Values: ``'down'``, ``'up'``, ``'up-down'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['staff-divide-symbol']


class XSDSimpleTypeStartStopChangeContinue(XSDSimpleTypeToken):
    """The start-stop-change-continue type is used to distinguish types of pedal directions.
    
    Permitted Values: ``'start'``, ``'stop'``, ``'change'``, ``'continue'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['start-stop-change-continue']


class XSDSimpleTypeSyncType(XSDSimpleTypeToken):
    """The sync-type type specifies the style that a score following application should use to synchronize an accompaniment with a performer. The none type indicates no synchronization to the performer. The tempo type indicates synchronization based on the performer tempo rather than individual events in the score. The event type indicates synchronization by following the performance of individual events in the score rather than the performer tempo. The mostly-tempo and mostly-event types combine these two approaches, with mostly-tempo giving more weight to tempo and mostly-event giving more weight to performed events. The always-event type provides the strictest synchronization by not being forgiving of missing performed events.
    
    Permitted Values: ``'none'``, ``'tempo'``, ``'mostly-tempo'``, ``'mostly-event'``, ``'event'``, ``'always-event'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['sync-type']


class XSDSimpleTypeSystemRelationNumber(XSDSimpleTypeString):
    """The system-relation-number type distinguishes measure numbers that are associated with a system rather than the particular part where the element appears. A value of only-top or only-bottom indicates that the number should appear only on the top or bottom part of the current system, respectively. A value of also-top or also-bottom indicates that the number should appear on both the current part and the top or bottom part of the current system, respectively. If these values appear in a score, when parts are created the number should only appear once in this part, not twice. A value of none indicates that the number is associated only with the current part, not with the system.
    
    Permitted Values: ``'only-top'``, ``'only-bottom'``, ``'also-top'``, ``'also-bottom'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['system-relation-number']


class XSDSimpleTypeSystemRelation(XSDSimpleTypeSystemRelationNumber):
    """The system-relation type distinguishes elements that are associated with a system rather than the particular part where the element appears. A value of only-top indicates that the element should appear only on the top part of the current system. A value of also-top indicates that the element should appear on both the current part and the top part of the current system. If this value appears in a score, when parts are created the element should only appear once in this part, not twice. A value of none indicates that the element is associated only with the current part, not with the system.
    
    Permitted Values: ``'only-top'``, ``'also-top'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['system-relation']


class XSDSimpleTypeTipDirection(XSDSimpleTypeString):
    """The tip-direction type represents the direction in which the tip of a stick or beater points, using Unicode arrow terminology.
    
    Permitted Values: ``'up'``, ``'down'``, ``'left'``, ``'right'``, ``'northwest'``, ``'northeast'``, ``'southeast'``, ``'southwest'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tip-direction']


class XSDSimpleTypeStickLocation(XSDSimpleTypeString):
    """The stick-location type represents pictograms for the location of sticks, beaters, or mallets on cymbals, gongs, drums, and other instruments.
    
    Permitted Values: ``'center'``, ``'rim'``, ``'cymbal bell'``, ``'cymbal edge'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['stick-location']


class XSDSimpleTypeStickMaterial(XSDSimpleTypeString):
    """The stick-material type represents the material being displayed in a stick pictogram.
    
    Permitted Values: ``'soft'``, ``'medium'``, ``'hard'``, ``'shaded'``, ``'x'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['stick-material']


class XSDSimpleTypeStickType(XSDSimpleTypeString):
    """The stick-type type represents the shape of pictograms where the material in the stick, mallet, or beater is represented in the pictogram.
    
    Permitted Values: ``'bass drum'``, ``'double bass drum'``, ``'glockenspiel'``, ``'gum'``, ``'hammer'``, ``'superball'``, ``'timpani'``, ``'wound'``, ``'xylophone'``, ``'yarn'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['stick-type']


class XSDSimpleTypeUpDownStopContinue(XSDSimpleTypeToken):
    """The up-down-stop-continue type is used for octave-shift elements, indicating the direction of the shift from their true pitched values because of printing difficulty.
    
    Permitted Values: ``'up'``, ``'down'``, ``'stop'``, ``'continue'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['up-down-stop-continue']


class XSDSimpleTypeWedgeType(XSDSimpleTypeToken):
    """The wedge type is crescendo for the start of a wedge that is closed at the left side, diminuendo for the start of a wedge that is closed on the right side, and stop for the end of a wedge. The continue type is used for formatting wedges over a system break, or for other situations where a single wedge is divided into multiple segments.
    
    Permitted Values: ``'crescendo'``, ``'diminuendo'``, ``'stop'``, ``'continue'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['wedge-type']


class XSDSimpleTypeWoodValue(XSDSimpleTypeString):
    """The wood-value type represents pictograms for wood percussion instruments. The maraca and maracas values distinguish the one- and two-maraca versions of the pictogram.
    
    Permitted Values: ``'bamboo scraper'``, ``'board clapper'``, ``'cabasa'``, ``'castanets'``, ``'castanets with handle'``, ``'claves'``, ``'football rattle'``, ``'guiro'``, ``'log drum'``, ``'maraca'``, ``'maracas'``, ``'quijada'``, ``'rainstick'``, ``'ratchet'``, ``'reco-reco'``, ``'sandpaper blocks'``, ``'slit drum'``, ``'temple block'``, ``'vibraslap'``, ``'whip'``, ``'wood block'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['wood-value']


class XSDSimpleTypeDistanceType(XSDSimpleTypeToken):
    """The distance-type defines what type of distance is being defined in a distance element. Values include beam and hyphen. This is left as a string so that other application-specific types can be defined, but it is made a separate type so that it can be redefined more strictly."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['distance-type']


class XSDSimpleTypeGlyphType(XSDSimpleTypeToken):
    """The glyph-type defines what type of glyph is being defined in a glyph element. Values include quarter-rest, g-clef-ottava-bassa, c-clef, f-clef, percussion-clef, octave-shift-up-8, octave-shift-down-8, octave-shift-continue-8, octave-shift-down-15, octave-shift-up-15, octave-shift-continue-15, octave-shift-down-22, octave-shift-up-22, and octave-shift-continue-22. This is left as a string so that other application-specific types can be defined, but it is made a separate type so that it can be redefined more strictly.

A quarter-rest type specifies the glyph to use when a note has a rest element and a type value of quarter. The c-clef, f-clef, and percussion-clef types specify the glyph to use when a clef sign element value is C, F, or percussion respectively. The g-clef-ottava-bassa type specifies the glyph to use when a clef sign element value is G and the clef-octave-change element value is -1. The octave-shift types specify the glyph to use when an octave-shift type attribute value is up, down, or continue and the octave-shift size attribute value is 8, 15, or 22."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['glyph-type']


class XSDSimpleTypeLineWidthType(XSDSimpleTypeToken):
    """The line-width-type defines what type of line is being defined in a line-width element. Values include beam, bracket, dashes, enclosure, ending, extend, heavy barline, leger, light barline, octave shift, pedal, slur middle, slur tip, staff, stem, tie middle, tie tip, tuplet bracket, and wedge. This is left as a string so that other application-specific types can be defined, but it is made a separate type so that it can be redefined more strictly."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['line-width-type']


class XSDSimpleTypeMarginType(XSDSimpleTypeToken):
    """The margin-type type specifies whether margins apply to even page, odd pages, or both.
    
    Permitted Values: ``'odd'``, ``'even'``, ``'both'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['margin-type']


class XSDSimpleTypeMillimeters(XSDSimpleTypeDecimal):
    """The millimeters type is a number representing millimeters. This is used in the scaling element to provide a default scaling from tenths to physical units."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['millimeters']


class XSDSimpleTypeNoteSizeType(XSDSimpleTypeToken):
    """The note-size-type type indicates the type of note being defined by a note-size element. The grace-cue type is used for notes of grace-cue size. The grace type is used for notes of cue size that include a grace element. The cue type is used for all other notes with cue size, whether defined explicitly or implicitly via a cue element. The large type is used for notes of large size.
    
    Permitted Values: ``'cue'``, ``'grace'``, ``'grace-cue'``, ``'large'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['note-size-type']


class XSDSimpleTypeAccidentalValue(XSDSimpleTypeString):
    """The accidental-value type represents notated accidentals supported by MusicXML. In the MusicXML 2.0 DTD this was a string with values that could be included. The XSD strengthens the data typing to an enumerated list. The quarter- and three-quarters- accidentals are Tartini-style quarter-tone accidentals. The -down and -up accidentals are quarter-tone accidentals that include arrows pointing down or up. The slash- accidentals are used in Turkish classical music. The numbered sharp and flat accidentals are superscripted versions of the accidental signs, used in Turkish folk music. The sori and koron accidentals are microtonal sharp and flat accidentals used in Iranian and Persian music. The other accidental covers accidentals other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL accidental. The smufl attribute may be used with any accidental value to help specify the appearance of symbols that share the same MusicXML semantics.
    
    Permitted Values: ``'sharp'``, ``'natural'``, ``'flat'``, ``'double-sharp'``, ``'sharp-sharp'``, ``'flat-flat'``, ``'natural-sharp'``, ``'natural-flat'``, ``'quarter-flat'``, ``'quarter-sharp'``, ``'three-quarters-flat'``, ``'three-quarters-sharp'``, ``'sharp-down'``, ``'sharp-up'``, ``'natural-down'``, ``'natural-up'``, ``'flat-down'``, ``'flat-up'``, ``'double-sharp-down'``, ``'double-sharp-up'``, ``'flat-flat-down'``, ``'flat-flat-up'``, ``'arrow-down'``, ``'arrow-up'``, ``'triple-sharp'``, ``'triple-flat'``, ``'slash-quarter-sharp'``, ``'slash-sharp'``, ``'slash-flat'``, ``'double-slash-flat'``, ``'sharp-1'``, ``'sharp-2'``, ``'sharp-3'``, ``'sharp-5'``, ``'flat-1'``, ``'flat-2'``, ``'flat-3'``, ``'flat-4'``, ``'sori'``, ``'koron'``, ``'other'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['accidental-value']


class XSDSimpleTypeArrowDirection(XSDSimpleTypeString):
    """The arrow-direction type represents the direction in which an arrow points, using Unicode arrow terminology.
    
    Permitted Values: ``'left'``, ``'up'``, ``'right'``, ``'down'``, ``'northwest'``, ``'northeast'``, ``'southeast'``, ``'southwest'``, ``'left right'``, ``'up down'``, ``'northwest southeast'``, ``'northeast southwest'``, ``'other'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['arrow-direction']


class XSDSimpleTypeArrowStyle(XSDSimpleTypeString):
    """The arrow-style type represents the style of an arrow, using Unicode arrow terminology. Filled and hollow arrows indicate polygonal single arrows. Paired arrows are duplicate single arrows in the same direction. Combined arrows apply to double direction arrows like left right, indicating that an arrow in one direction should be combined with an arrow in the other direction.
    
    Permitted Values: ``'single'``, ``'double'``, ``'filled'``, ``'hollow'``, ``'paired'``, ``'combined'``, ``'other'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['arrow-style']


class XSDSimpleTypeBeamValue(XSDSimpleTypeString):
    """The beam-value type represents the type of beam associated with each of 8 beam levels (up to 1024th notes) available for each note.
    
    Permitted Values: ``'begin'``, ``'continue'``, ``'end'``, ``'forward hook'``, ``'backward hook'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['beam-value']


class XSDSimpleTypeBendShape(XSDSimpleTypeString):
    """The bend-shape type distinguishes between the angled bend symbols commonly used in standard notation and the curved bend symbols commonly used in both tablature and standard notation.
    
    Permitted Values: ``'angled'``, ``'curved'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['bend-shape']


class XSDSimpleTypeBreathMarkValue(XSDSimpleTypeString):
    """The breath-mark-value type represents the symbol used for a breath mark.
    
    Permitted Values: ``''``, ``'comma'``, ``'tick'``, ``'upbow'``, ``'salzedo'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['breath-mark-value']


class XSDSimpleTypeCaesuraValue(XSDSimpleTypeString):
    """The caesura-value type represents the shape of the caesura sign.
    
    Permitted Values: ``'normal'``, ``'thick'``, ``'short'``, ``'curved'``, ``'single'``, ``''``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['caesura-value']


class XSDSimpleTypeCircularArrow(XSDSimpleTypeString):
    """The circular-arrow type represents the direction in which a circular arrow points, using Unicode arrow terminology.
    
    Permitted Values: ``'clockwise'``, ``'anticlockwise'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['circular-arrow']


class XSDSimpleTypeFan(XSDSimpleTypeToken):
    """The fan type represents the type of beam fanning present on a note, used to represent accelerandos and ritardandos.
    
    Permitted Values: ``'accel'``, ``'rit'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['fan']


class XSDSimpleTypeHandbellValue(XSDSimpleTypeString):
    """The handbell-value type represents the type of handbell technique being notated.
    
    Permitted Values: ``'belltree'``, ``'damp'``, ``'echo'``, ``'gyro'``, ``'hand martellato'``, ``'mallet lift'``, ``'mallet table'``, ``'martellato'``, ``'martellato lift'``, ``'muted martellato'``, ``'pluck lift'``, ``'swing'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['handbell-value']


class XSDSimpleTypeHarmonClosedLocation(XSDSimpleTypeString):
    """The harmon-closed-location type indicates which portion of the symbol is filled in when the corresponding harmon-closed-value is half.
    
    Permitted Values: ``'right'``, ``'bottom'``, ``'left'``, ``'top'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['harmon-closed-location']


class XSDSimpleTypeHarmonClosedValue(XSDSimpleTypeString):
    """The harmon-closed-value type represents whether the harmon mute is closed, open, or half-open.
    
    Permitted Values: ``'yes'``, ``'no'``, ``'half'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['harmon-closed-value']


class XSDSimpleTypeHoleClosedLocation(XSDSimpleTypeString):
    """The hole-closed-location type indicates which portion of the hole is filled in when the corresponding hole-closed-value is half.
    
    Permitted Values: ``'right'``, ``'bottom'``, ``'left'``, ``'top'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['hole-closed-location']


class XSDSimpleTypeHoleClosedValue(XSDSimpleTypeString):
    """The hole-closed-value type represents whether the hole is closed, open, or half-open.
    
    Permitted Values: ``'yes'``, ``'no'``, ``'half'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['hole-closed-value']


class XSDSimpleTypeNoteTypeValue(XSDSimpleTypeString):
    """The note-type-value type is used for the MusicXML type element and represents the graphic note type, from 1024th (shortest) to maxima (longest).
    
    Permitted Values: ``'1024th'``, ``'512th'``, ``'256th'``, ``'128th'``, ``'64th'``, ``'32nd'``, ``'16th'``, ``'eighth'``, ``'quarter'``, ``'half'``, ``'whole'``, ``'breve'``, ``'long'``, ``'maxima'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['note-type-value']


class XSDSimpleTypeNoteheadValue(XSDSimpleTypeString):
    """The notehead-value type indicates shapes other than the open and closed ovals associated with note durations. 

The values do, re, mi, fa, fa up, so, la, and ti correspond to Aikin's 7-shape system.  The fa up shape is typically used with upstems; the fa shape is typically used with downstems or no stems.

The arrow shapes differ from triangle and inverted triangle by being centered on the stem. Slashed and back slashed notes include both the normal notehead and a slash. The triangle shape has the tip of the triangle pointing up; the inverted triangle shape has the tip of the triangle pointing down. The left triangle shape is a right triangle with the hypotenuse facing up and to the left.

The other notehead covers noteheads other than those listed here. It is usually used in combination with the smufl attribute to specify a particular SMuFL notehead. The smufl attribute may be used with any notehead value to help specify the appearance of symbols that share the same MusicXML semantics. Noteheads in the SMuFL Note name noteheads and Note name noteheads supplement ranges (U+E150–U+E1AF and U+EEE0–U+EEFF) should not use the smufl attribute or the "other" value, but instead use the notehead-text element.
    
    Permitted Values: ``'slash'``, ``'triangle'``, ``'diamond'``, ``'square'``, ``'cross'``, ``'x'``, ``'circle-x'``, ``'inverted triangle'``, ``'arrow down'``, ``'arrow up'``, ``'circled'``, ``'slashed'``, ``'back slashed'``, ``'normal'``, ``'cluster'``, ``'circle dot'``, ``'left triangle'``, ``'rectangle'``, ``'none'``, ``'do'``, ``'re'``, ``'mi'``, ``'fa'``, ``'fa up'``, ``'so'``, ``'la'``, ``'ti'``, ``'other'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['notehead-value']


class XSDSimpleTypeOctave(XSDSimpleTypeInteger):
    """Octaves are represented by the numbers 0 to 9, where 4 indicates the octave started by middle C."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['octave']


class XSDSimpleTypeSemitones(XSDSimpleTypeDecimal):
    """The semitones type is a number representing semitones, used for chromatic alteration. A value of -1 corresponds to a flat and a value of 1 to a sharp. Decimal values like 0.5 (quarter tone sharp) are used for microtones."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['semitones']


class XSDSimpleTypeShowTuplet(XSDSimpleTypeToken):
    """The show-tuplet type indicates whether to show a part of a tuplet relating to the tuplet-actual element, both the tuplet-actual and tuplet-normal elements, or neither.
    
    Permitted Values: ``'actual'``, ``'both'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['show-tuplet']


class XSDSimpleTypeStemValue(XSDSimpleTypeString):
    """The stem-value type represents the notated stem direction.
    
    Permitted Values: ``'down'``, ``'up'``, ``'double'``, ``'none'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['stem-value']


class XSDSimpleTypeStep(XSDSimpleTypeString):
    """The step type represents a step of the diatonic scale, represented using the English letters A through G.
    
    Permitted Values: ``'A'``, ``'B'``, ``'C'``, ``'D'``, ``'E'``, ``'F'``, ``'G'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['step']


class XSDSimpleTypeSyllabic(XSDSimpleTypeString):
    """Lyric hyphenation is indicated by the syllabic type. The single, begin, end, and middle values represent single-syllable words, word-beginning syllables, word-ending syllables, and mid-word syllables, respectively.
    
    Permitted Values: ``'single'``, ``'begin'``, ``'end'``, ``'middle'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['syllabic']


class XSDSimpleTypeTapHand(XSDSimpleTypeString):
    """The tap-hand type represents the symbol to use for a tap element. The left and right values refer to the SMuFL guitarLeftHandTapping and guitarRightHandTapping glyphs respectively.
    
    Permitted Values: ``'left'``, ``'right'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tap-hand']


class XSDSimpleTypeTremoloMarks(XSDSimpleTypeInteger):
    """The number of tremolo marks is represented by a number from 0 to 8: the same as beam-level with 0 added."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['tremolo-marks']


class XSDSimpleTypeGroupBarlineValue(XSDSimpleTypeString):
    """The group-barline-value type indicates if the group should have common barlines.
    
    Permitted Values: ``'yes'``, ``'no'``, ``'Mensurstrich'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['group-barline-value']


class XSDSimpleTypeGroupSymbolValue(XSDSimpleTypeString):
    """The group-symbol-value type indicates how the symbol for a group or multi-staff part is indicated in the score.
    
    Permitted Values: ``'none'``, ``'brace'``, ``'line'``, ``'bracket'``, ``'square'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['group-symbol-value']


class XSDSimpleTypeMeasureText(XSDSimpleTypeToken):
    """The measure-text type is used for the text attribute of measure elements. It has at least one character. The implicit attribute of the measure element should be set to "yes" rather than setting the text attribute to an empty string."""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['measure-text']


class XSDSimpleTypeSwingTypeValue(XSDSimpleTypeNoteTypeValue):
    """The swing-type-value type specifies the note type, either eighth or 16th, to which the ratio defined in the swing element is applied.
    
    Permitted Values: ``'16th'``, ``'eighth'``
"""
    _XSD_TREE = XSD_TREE_DICT['simpleType']['swing-type-value']

class XSDSimpleTypeFontSize(XSDSimpleType):
    """The font-size can be one of the CSS font sizes (xx-small, x-small, small, medium, large, x-large, xx-large) or a numeric point size.

    .. todo::
       Better documentation.
    """
    _UNION = [XSDSimpleTypeCssFontSize, XSDSimpleTypeDecimal]
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="font-size">
    <xs:annotation>
        <xs:documentation>The font-size can be one of the CSS font sizes (xx-small, x-small, small, medium, large, x-large, xx-large) or a numeric point size.</xs:documentation>
    </xs:annotation>
    <xs:union memberTypes="xs:decimal css-font-size" />
</xs:simpleType>
"""
                                     ))


class XSDSimpleTypeYesNoNumber(XSDSimpleType):
    """The yes-no-number type is used for attributes that can be either boolean or numeric values.

    .. todo::
       Better documentation.
    """
    _UNION = [XSDSimpleTypeYesNo, XSDSimpleTypeDecimal]
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="yes-no-number">
    <xs:annotation>
        <xs:documentation>The yes-no-number type is used for attributes that can be either boolean or numeric values.</xs:documentation>
    </xs:annotation>
    <xs:union memberTypes="yes-no xs:decimal" />
</xs:simpleType>
"""
                                     ))


class XSDSimpleTypePositiveIntegerOrEmpty(XSDSimpleTypePositiveInteger):
    """The positive-integer-or-empty values can be either a positive integer or an empty string.

    .. todo::
       Better documentation.
    """
    _FORCED_PERMITTED = ['']
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="positive-integer-or-empty">
    <xs:annotation>
        <xs:documentation>The positive-integer-or-empty values can be either a positive integer or an empty string.</xs:documentation>
    </xs:annotation>
    <xs:union memberTypes="xs:positiveInteger">
        <xs:simpleType>
            <xs:restriction base="xs:string">
                <xs:enumeration value="" />
            </xs:restriction>
        </xs:simpleType>
    </xs:union>
</xs:simpleType>
"""
                                     ))

    def __init__(self, value='', *args, **kwargs):
        super().__init__(value=value, *args, **kwargs)


class XSDSimpleTypeNumberOrNormal(XSDSimpleTypeDecimal):
    """The number-or-normal values can be either a decimal number or the string "normal". This is used by the line-height and letter-spacing attributes.

    .. todo::
       Better documentation.
    """
    _FORCED_PERMITTED = ['normal']
    XSD_TREE = XSDTree(ET.fromstring("""
<xs:simpleType xmlns:xs="http://www.w3.org/2001/XMLSchema" name="number-or-normal">
    <xs:annotation>
        <xs:documentation>The number-or-normal values can be either a decimal number or the string "normal". This is used by the line-height and letter-spacing attributes.</xs:documentation>
    </xs:annotation>
    <xs:union memberTypes="xs:decimal">
        <xs:simpleType>
            <xs:restriction base="xs:token">
                <xs:enumeration value="normal" />
            </xs:restriction>
        </xs:simpleType>
    </xs:union>
</xs:simpleType>
"""
                                     ))

__all__=['XSDSimpleType', 'XSDSimpleTypeInteger', 'XSDSimpleTypeNonNegativeInteger', 'XSDSimpleTypePositiveInteger', 'XSDSimpleTypeDecimal', 'XSDSimpleTypeString', 'XSDSimpleTypeToken', 'XSDSimpleTypeDate', 'XSDSimpleTypeNumberOrNormal', 'XSDSimpleTypePositiveIntegerOrEmpty', 'XSDSimpleTypeFontSize', 'XSDSimpleTypeYesNoNumber', 'XSDSimpleTypeNMTOKEN', 'XSDSimpleTypeName', 'XSDSimpleTypeNCName', 'XSDSimpleTypeID', 'XSDSimpleTypeIDREF', 'XSDSimpleTypeLanguage', 'XSDSimpleTypeAboveBelow', 'XSDSimpleTypeBeamLevel', 'XSDSimpleTypeColor', 'XSDSimpleTypeCommaSeparatedText', 'XSDSimpleTypeCssFontSize', 'XSDSimpleTypeDivisions', 'XSDSimpleTypeEnclosureShape', 'XSDSimpleTypeFermataShape', 'XSDSimpleTypeFontFamily', 'XSDSimpleTypeFontStyle', 'XSDSimpleTypeFontWeight', 'XSDSimpleTypeLeftCenterRight', 'XSDSimpleTypeLeftRight', 'XSDSimpleTypeLineLength', 'XSDSimpleTypeLineShape', 'XSDSimpleTypeLineType', 'XSDSimpleTypeMidi16', 'XSDSimpleTypeMidi128', 'XSDSimpleTypeMidi16384', 'XSDSimpleTypeMute', 'XSDSimpleTypeNonNegativeDecimal', 'XSDSimpleTypeNumberLevel', 'XSDSimpleTypeNumberOfLines', 'XSDSimpleTypeNumeralValue', 'XSDSimpleTypeOverUnder', 'XSDSimpleTypePercent', 'XSDSimpleTypePositiveDecimal', 'XSDSimpleTypePositiveDivisions', 'XSDSimpleTypeRotationDegrees', 'XSDSimpleTypeSemiPitched', 'XSDSimpleTypeSmuflGlyphName', 'XSDSimpleTypeSmuflAccidentalGlyphName', 'XSDSimpleTypeSmuflCodaGlyphName', 'XSDSimpleTypeSmuflLyricsGlyphName', 'XSDSimpleTypeSmuflPictogramGlyphName', 'XSDSimpleTypeSmuflSegnoGlyphName', 'XSDSimpleTypeSmuflWavyLineGlyphName', 'XSDSimpleTypeStartNote', 'XSDSimpleTypeStartStop', 'XSDSimpleTypeStartStopContinue', 'XSDSimpleTypeStartStopSingle', 'XSDSimpleTypeStringNumber', 'XSDSimpleTypeSymbolSize', 'XSDSimpleTypeTenths', 'XSDSimpleTypeTextDirection', 'XSDSimpleTypeTiedType', 'XSDSimpleTypeTimeOnly', 'XSDSimpleTypeTopBottom', 'XSDSimpleTypeTremoloType', 'XSDSimpleTypeTrillBeats', 'XSDSimpleTypeTrillStep', 'XSDSimpleTypeTwoNoteTurn', 'XSDSimpleTypeUpDown', 'XSDSimpleTypeUprightInverted', 'XSDSimpleTypeValign', 'XSDSimpleTypeValignImage', 'XSDSimpleTypeYesNo', 'XSDSimpleTypeYyyyMmDd', 'XSDSimpleTypeCancelLocation', 'XSDSimpleTypeClefSign', 'XSDSimpleTypeFifths', 'XSDSimpleTypeMode', 'XSDSimpleTypeShowFrets', 'XSDSimpleTypeStaffLine', 'XSDSimpleTypeStaffLinePosition', 'XSDSimpleTypeStaffNumber', 'XSDSimpleTypeStaffType', 'XSDSimpleTypeTimeRelation', 'XSDSimpleTypeTimeSeparator', 'XSDSimpleTypeTimeSymbol', 'XSDSimpleTypeBackwardForward', 'XSDSimpleTypeBarStyle', 'XSDSimpleTypeEndingNumber', 'XSDSimpleTypeRightLeftMiddle', 'XSDSimpleTypeStartStopDiscontinue', 'XSDSimpleTypeWinged', 'XSDSimpleTypeAccordionMiddle', 'XSDSimpleTypeBeaterValue', 'XSDSimpleTypeDegreeSymbolValue', 'XSDSimpleTypeDegreeTypeValue', 'XSDSimpleTypeEffectValue', 'XSDSimpleTypeGlassValue', 'XSDSimpleTypeHarmonyArrangement', 'XSDSimpleTypeHarmonyType', 'XSDSimpleTypeKindValue', 'XSDSimpleTypeLineEnd', 'XSDSimpleTypeMeasureNumberingValue', 'XSDSimpleTypeMembraneValue', 'XSDSimpleTypeMetalValue', 'XSDSimpleTypeMilliseconds', 'XSDSimpleTypeNumeralMode', 'XSDSimpleTypeOnOff', 'XSDSimpleTypePedalType', 'XSDSimpleTypePitchedValue', 'XSDSimpleTypePrincipalVoiceSymbol', 'XSDSimpleTypeStaffDivideSymbol', 'XSDSimpleTypeStartStopChangeContinue', 'XSDSimpleTypeSyncType', 'XSDSimpleTypeSystemRelationNumber', 'XSDSimpleTypeSystemRelation', 'XSDSimpleTypeTipDirection', 'XSDSimpleTypeStickLocation', 'XSDSimpleTypeStickMaterial', 'XSDSimpleTypeStickType', 'XSDSimpleTypeUpDownStopContinue', 'XSDSimpleTypeWedgeType', 'XSDSimpleTypeWoodValue', 'XSDSimpleTypeDistanceType', 'XSDSimpleTypeGlyphType', 'XSDSimpleTypeLineWidthType', 'XSDSimpleTypeMarginType', 'XSDSimpleTypeMillimeters', 'XSDSimpleTypeNoteSizeType', 'XSDSimpleTypeAccidentalValue', 'XSDSimpleTypeArrowDirection', 'XSDSimpleTypeArrowStyle', 'XSDSimpleTypeBeamValue', 'XSDSimpleTypeBendShape', 'XSDSimpleTypeBreathMarkValue', 'XSDSimpleTypeCaesuraValue', 'XSDSimpleTypeCircularArrow', 'XSDSimpleTypeFan', 'XSDSimpleTypeHandbellValue', 'XSDSimpleTypeHarmonClosedLocation', 'XSDSimpleTypeHarmonClosedValue', 'XSDSimpleTypeHoleClosedLocation', 'XSDSimpleTypeHoleClosedValue', 'XSDSimpleTypeNoteTypeValue', 'XSDSimpleTypeNoteheadValue', 'XSDSimpleTypeOctave', 'XSDSimpleTypeSemitones', 'XSDSimpleTypeShowTuplet', 'XSDSimpleTypeStemValue', 'XSDSimpleTypeStep', 'XSDSimpleTypeSyllabic', 'XSDSimpleTypeTapHand', 'XSDSimpleTypeTremoloMarks', 'XSDSimpleTypeGroupBarlineValue', 'XSDSimpleTypeGroupSymbolValue', 'XSDSimpleTypeMeasureText', 'XSDSimpleTypeSwingTypeValue']
