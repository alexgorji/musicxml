from musicxml.util.core import cap_first, convert_to_xml_class_name
from musicxml.xsd.xsdtree import XSDTree, XSDTreeElement, XSD_TREE_DICT
import xml.etree.ElementTree as ET


class XSDSequence:
    def __init__(self, xsd_tree):
        self._xsd_tree = None
        self._elements = None
        self.xsd_tree = xsd_tree

    @property
    def elements(self):
        if not self._elements:
            self._elements = []
            for child in self.xsd_tree.get_children():
                if child.tag == 'element':
                    element = convert_to_xml_class_name(child.name)
                    min_occurrence = child.get_attributes().get('minOccurs')
                    if min_occurrence is None: min_occurrence = '1'
                    max_occurrence = child.get_attributes().get('maxOccurs')
                    if max_occurrence is None: max_occurrence = '1'
                    self._elements.append((element, min_occurrence, max_occurrence))

                elif child.tag == 'group':
                    xsd_group_name = 'XSDGroup' + ''.join([cap_first(partial) for partial in child.get_attributes()['ref'].split('-')])
                    elements = eval(xsd_group_name)().sequence.elements
                    min_occurrence = child.get_attributes().get('minOccurs')
                    max_occurrence = child.get_attributes().get('maxOccurs')
                    if min_occurrence is not None:
                        if len(elements) > 1:
                            raise NotImplementedError
                        list_el = list(elements[0])
                        list_el[1] = min_occurrence
                        elements[0] = tuple(list_el)
                    if max_occurrence is not None:
                        if len(elements) > 1:
                            raise NotImplementedError
                        list_el = list(elements[0])
                        list_el[2] = max_occurrence
                        elements[0] = tuple(list_el)
                    self._elements.extend(elements)
                else:
                    raise NotImplementedError(child.tag)
        return self._elements

    @property
    def xsd_tree(self):
        return self._xsd_tree

    @xsd_tree.setter
    def xsd_tree(self, value):
        if not isinstance(value, XSDTree):
            raise TypeError
        if value.tag != 'sequence':
            raise ValueError
        self._xsd_tree = value

    def __copy__(self):
        return self.__class__(xsd_tree=self.xsd_tree)


class XSDChoice:
    def __init__(self, xsd_tree):
        self._xsd_tree = None
        self.xsd_tree = xsd_tree

    @property
    def xsd_tree(self):
        return self._xsd_tree

    @xsd_tree.setter
    def xsd_tree(self, value):
        if not isinstance(value, XSDTree):
            raise TypeError
        if value.tag != 'choice':
            raise ValueError
        self._xsd_tree = value

    def __copy__(self):
        return self.__class__(xsd_tree=self.xsd_tree)


class XSDGroup(XSDTreeElement):

    def __init__(self):
        self._sequence = None

    @property
    def name(self):
        return self.XSD_TREE.name

    @property
    def sequence(self):
        if not self._sequence:
            for child in self.XSD_TREE.get_children():
                if child.tag == 'sequence':
                    self._sequence = XSDSequence(child)
        return self._sequence

    @property
    def xsd_tree(self):
        return self.XSD_TREE

    def __copy__(self):
        copied = self.__class__()
        copied._sequence = self.sequence
        copied.XSD_TREE = self.XSD_TREE
        return copied
# -----------------------------------------------------
# AUTOMATICALLY GENERATED WITH generate_indicators.py
# -----------------------------------------------------


class XSDGroupEditorial(XSDGroup):
    """The editorial group specifies editorial information for a musical element."""
    
    XSD_TREE = XSD_TREE_DICT['group']['editorial']


class XSDGroupEditorialVoice(XSDGroup):
    """The editorial-voice group supports the common combination of editorial and voice information for a musical element."""
    
    XSD_TREE = XSD_TREE_DICT['group']['editorial-voice']


class XSDGroupEditorialVoiceDirection(XSDGroup):
    """The editorial-voice-direction group supports the common combination of editorial and voice information for a direction element. It is separate from the editorial-voice element because extensions and restrictions might be different for directions than for the note and forward elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['editorial-voice-direction']


class XSDGroupFootnote(XSDGroup):
    """The footnote element specifies editorial information that appears in footnotes in the printed score. It is defined within a group due to its multiple uses within the MusicXML schema."""
    
    XSD_TREE = XSD_TREE_DICT['group']['footnote']


class XSDGroupLevel(XSDGroup):
    """The level element specifies editorial information for different MusicXML elements. It is defined within a group due to its multiple uses within the MusicXML schema."""
    
    XSD_TREE = XSD_TREE_DICT['group']['level']


class XSDGroupStaff(XSDGroup):
    """The staff element is defined within a group due to its use by both notes and direction elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['staff']


class XSDGroupTuning(XSDGroup):
    """The tuning group contains the sequence of elements common to the staff-tuning and accord elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['tuning']


class XSDGroupVirtualInstrumentData(XSDGroup):
    """Virtual instrument data can be part of either the score-instrument element at the start of a part, or an instrument-change element within a part."""
    
    XSD_TREE = XSD_TREE_DICT['group']['virtual-instrument-data']


class XSDGroupVoice(XSDGroup):
    """A voice is a sequence of musical events (e.g. notes, chords, rests) that proceeds linearly in time. The voice element is used to distinguish between multiple voices in individual parts. It is defined within a group due to its multiple uses within the MusicXML schema."""
    
    XSD_TREE = XSD_TREE_DICT['group']['voice']


class XSDGroupClef(XSDGroup):
    """Clefs are represented by a combination of sign, line, and clef-octave-change elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['clef']


class XSDGroupNonTraditionalKey(XSDGroup):
    """The non-traditional-key group represents a single alteration within a non-traditional key signature. A sequence of these groups makes up a non-traditional key signature"""
    
    XSD_TREE = XSD_TREE_DICT['group']['non-traditional-key']


class XSDGroupSlash(XSDGroup):
    """The slash group combines elements used for more complete specification of the slash and beat-repeat measure-style elements. They have the same values as the type and dot elements, and define what the beat is for the display of repetition marks. If not present, the beat is based on the current time signature."""
    
    XSD_TREE = XSD_TREE_DICT['group']['slash']


class XSDGroupTimeSignature(XSDGroup):
    """Time signatures are represented by the beats element for the numerator and the beat-type element for the denominator."""
    
    XSD_TREE = XSD_TREE_DICT['group']['time-signature']


class XSDGroupTraditionalKey(XSDGroup):
    """The traditional-key group represents a traditional key signature using the cycle of fifths."""
    
    XSD_TREE = XSD_TREE_DICT['group']['traditional-key']


class XSDGroupTranspose(XSDGroup):
    """The transpose group represents what must be added to a written pitch to get a correct sounding pitch."""
    
    XSD_TREE = XSD_TREE_DICT['group']['transpose']


class XSDGroupBeatUnit(XSDGroup):
    """The beat-unit group combines elements used repeatedly in the metronome element to specify a note within a metronome mark."""
    
    XSD_TREE = XSD_TREE_DICT['group']['beat-unit']


class XSDGroupHarmonyChord(XSDGroup):
    """A harmony element can contain many stacked chords (e.g. V of II). A sequence of harmony-chord groups is used for this type of secondary function, where V of II would be represented by a harmony-chord with a 5 numeral followed by a harmony-chord with a 2 numeral.

A root is a pitch name like C, D, E, while a numeral is a scale degree like 1, 2, 3. The root element is generally used with pop chord symbols, while the numeral element is generally used with classical functional harmony and Nashville numbers. It is an either/or choice to avoid data inconsistency. The function element, which represents Roman numerals with roman numeral text, has been deprecated as of MusicXML 4.0."""
    
    XSD_TREE = XSD_TREE_DICT['group']['harmony-chord']


class XSDGroupAllMargins(XSDGroup):
    """The all-margins group specifies both horizontal and vertical margins in tenths."""
    
    XSD_TREE = XSD_TREE_DICT['group']['all-margins']


class XSDGroupLayout(XSDGroup):
    """The layout group specifies the sequence of page, system, and staff layout elements that is common to both the defaults and print elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['layout']


class XSDGroupLeftRightMargins(XSDGroup):
    """The left-right-margins group specifies horizontal margins in tenths."""
    
    XSD_TREE = XSD_TREE_DICT['group']['left-right-margins']


class XSDGroupDuration(XSDGroup):
    """The duration element is defined within a group due to its uses within the note, figured-bass, backup, and forward elements."""
    
    XSD_TREE = XSD_TREE_DICT['group']['duration']


class XSDGroupDisplayStepOctave(XSDGroup):
    """The display-step-octave group contains the sequence of elements used by both the rest and unpitched elements. This group is used to place rests and unpitched elements on the staff without implying that these elements have pitch. Positioning follows the current clef. If percussion clef is used, the display-step and display-octave elements are interpreted as if in treble clef, with a G in octave 4 on line 2."""
    
    XSD_TREE = XSD_TREE_DICT['group']['display-step-octave']


class XSDGroupFullNote(XSDGroup):
    """The full-note group is a sequence of the common note elements between cue/grace notes and regular (full) notes: pitch, chord, and rest information, but not duration (cue and grace notes do not have duration encoded). Unpitched elements are used for unpitched percussion, speaking voice, and other musical elements lacking determinate pitch."""
    
    XSD_TREE = XSD_TREE_DICT['group']['full-note']


class XSDGroupMusicData(XSDGroup):
    """The music-data group contains the basic musical data that is either associated with a part or a measure, depending on whether the partwise or timewise hierarchy is used."""
    
    XSD_TREE = XSD_TREE_DICT['group']['music-data']


class XSDGroupPartGroup(XSDGroup):
    """The part-group element is defined within a group due to its multiple uses within the part-list element."""
    
    XSD_TREE = XSD_TREE_DICT['group']['part-group']


class XSDGroupScoreHeader(XSDGroup):
    """The score-header group contains basic score metadata about the work and movement, score-wide defaults for layout and fonts, credits that appear on the first or following pages, and the part list."""
    
    XSD_TREE = XSD_TREE_DICT['group']['score-header']


class XSDGroupScorePart(XSDGroup):
    """The score-part element is defined within a group due to its multiple uses within the part-list element."""
    
    XSD_TREE = XSD_TREE_DICT['group']['score-part']

__all__=['XSDSequence', 'XSDChoice', 'XSDGroup', 'XSDGroupEditorial', 'XSDGroupEditorialVoice', 'XSDGroupEditorialVoiceDirection', 'XSDGroupFootnote', 'XSDGroupLevel', 'XSDGroupStaff', 'XSDGroupTuning', 'XSDGroupVirtualInstrumentData', 'XSDGroupVoice', 'XSDGroupClef', 'XSDGroupNonTraditionalKey', 'XSDGroupSlash', 'XSDGroupTimeSignature', 'XSDGroupTraditionalKey', 'XSDGroupTranspose', 'XSDGroupBeatUnit', 'XSDGroupHarmonyChord', 'XSDGroupAllMargins', 'XSDGroupLayout', 'XSDGroupLeftRightMargins', 'XSDGroupDuration', 'XSDGroupDisplayStepOctave', 'XSDGroupFullNote', 'XSDGroupMusicData', 'XSDGroupPartGroup', 'XSDGroupScoreHeader', 'XSDGroupScorePart']
