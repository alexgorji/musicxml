from copy import deepcopy
from pathlib import Path
from unittest import TestCase

from musicxml.xmlelement.xmlelement import *

parent_folder = Path(__file__).parent

class TestXMLDeepcopy(TestCase):
    def test_deepcopy_xml_measure(self):
        m = XMLMeasure(number='1')
        copied = deepcopy(m)
        self.assertEqual(m.to_string(), copied.to_string())

class TestDeepcopyScore(TestCase):
    def test_deepcopy_hello_world(self):
        score = XMLScorePartwise(version='3.1')
        pl = score.add_child(XMLPartList())
        sp = pl.add_child(XMLScorePart(id='P1'))
        sp.add_child(XMLPartName('Part 1', print_object='no'))
        p = score.add_child(XMLPart(id='P1'))
        m = p.add_child(XMLMeasure(number='1'))
        att = m.add_child(XMLAttributes())
        att.add_child(XMLDivisions(1))
        t = att.add_child(XMLTime())
        t.add_child(XMLBeats('4'))
        t.add_child(XMLBeatType('4'))
        c = att.add_child(XMLClef())
        c.add_child(XMLSign('G'))
        c.add_child(XMLLine(2))
        k = att.add_child(XMLKey())
        k.add_child(XMLFifths(0))
        k.add_child(XMLMode('major'))
        n = m.add_child(XMLNote())
        p = n.add_child(XMLPitch())
        p.add_child(XMLStep('C'))
        p.add_child(XMLOctave(4))
        n.add_child(XMLDuration(4))
        n.add_child(XMLVoice('1'))
        n.add_child(XMLType('whole'))
        bl = m.add_child(XMLBarline(location='right'))
        bl.add_child(XMLBarStyle('light-heavy'))

        copied = deepcopy(score)

        self.assertEqual(score.to_string(), copied.to_string())


