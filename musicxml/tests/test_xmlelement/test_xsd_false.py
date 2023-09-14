from unittest import TestCase

from musicxml.exceptions import XMLElementChildrenRequired
from musicxml.xmlelement.xmlelement import *


class TestXSDFalse(TestCase):
    def test_xml_element_with_xsd_false_simple(self):
        xml_score_part = XMLScorePart()
        with self.assertRaises(XMLElementChildrenRequired):
            xml_score_part.to_string()

        xml_score_part.xsd_check = False
        assert xml_score_part.to_string() == '<score-part />\n'

    def test_xml_part_list_xsd_false(self):
        xml_part_list = XMLPartList()
        with self.assertRaises(XMLElementChildrenRequired):
            xml_part_list.to_string()
        xml_part_list = XMLPartList(xsd_check=False)
        # xml_part_list.xsd_check = False
        assert xml_part_list.to_string() == '<part-list />\n'

        xml_part_list.add_child(XMLScorePart(id='p-1'))

        pg = xml_part_list.add_child(XMLPartGroup(number='1', type='start'))
        pg.add_child(XMLGroupSymbol('square'))
        pg.add_child(XMLGroupBarline('yes'))
        xml_part_list.add_child(XMLScorePart(id='p-2'))

        pg = xml_part_list.add_child(XMLPartGroup(number='2', type='start'))
        pg.add_child(XMLGroupSymbol('bracket'))
        pg.add_child(XMLGroupBarline('yes'))
        xml_part_list.add_child(XMLScorePart(id='p-3'))

        xml_part_list.add_child(XMLPartGroup(number='1', type='stop'))
        xml_part_list.add_child(XMLPartGroup(number='2', type='stop'))
        xml_part_list.add_child(XMLScorePart(id='p-4'))

        xml_part_list.add_child(XMLScorePart(id='p-5'))

        expected = """<part-list>
  <score-part id="p-1" />
  <part-group number="1" type="start">
    <group-symbol>square</group-symbol>
    <group-barline>yes</group-barline>
  </part-group>
  <score-part id="p-2" />
  <part-group number="2" type="start">
    <group-symbol>bracket</group-symbol>
    <group-barline>yes</group-barline>
  </part-group>
  <score-part id="p-3" />
  <part-group number="1" type="stop" />
  <part-group number="2" type="stop" />
  <score-part id="p-4" />
  <score-part id="p-5" />
</part-list>
"""

        assert xml_part_list.to_string() == expected

    def test_xml_part_list_init_xsd_false(self):
        xml_part_list = XMLPartList(xsd_check=False)
        assert xml_part_list.to_string() == '<part-list />\n'

    def test_xml_part_xsd_false_with_parent_xsd_true(self):
        xml_score = XMLScorePartwise()
        xml_part = xml_score.add_child(XMLPart(id='p1'))
        xml_part.add_child(XMLMeasure(number='1'))
        xml_part_list = XMLPartList(xsd_check=False)
        xml_score.add_child(xml_part_list)
        assert xml_part_list.to_string() == '<part-list />\n'
        print(xml_score.to_string())
