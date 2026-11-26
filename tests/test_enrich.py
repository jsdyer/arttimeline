import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from enrich import cma_record,nga_record,getty_record,jpeg_size,verify_pixels
class EnrichTests(unittest.TestCase):
 def test_cleveland_requires_individual_cc0_and_approved_images(self):
  raw={'id':10,'title':'A work','share_license_status':'CC0','images':{'web':{'url':'https://openaccess-cdn.clevelandart.org/w.jpg'},'print':{'url':'https://evil.example/x','width':'3400','height':'2000'}}}
  r=cma_record(raw,'today');self.assertTrue(r['image']);self.assertIsNone(r['pixelSize']);self.assertIsNone(r['start']);raw['share_license_status']='Copyright';self.assertFalse(cma_record(raw,'today')['image'])
 def test_nga_zero_identity_and_openaccess_flag(self):
  r=nga_record({'objectid':'0','title':'A work','beginyear':'1310','endyear':'1310'},{'openaccess':'0','iiifurl':'https://api.nga.gov/iiif/x','width':'1000','height':'2000'},'today');self.assertEqual(r['key'],'nga:0');self.assertFalse(r['image']);self.assertIsNone(r['pixelSize'])
 def test_getty_metadata_license_does_not_authorize_image(self):
  x={'id':'https://data.getty.edu/museum/collection/object/a','_label':'A work','subject_to':[{'_label':'CC0'}]};manifest={'id':'https://media.getty.edu/m','rights':'https://rightsstatements.org/vocab/InC/1.0/','items':[{'type':'Canvas','thumbnail':[{'id':'https://media.getty.edu/i.jpg'}]}]};r=getty_record(x,manifest,'today');self.assertFalse(r['image']);self.assertFalse(r['publicDomain'])
 def test_jpeg_actual_served_dimensions_override_export_dimensions(self):
  jpeg=b'\xff\xd8\xff\xe0\x00\x04xx\xff\xc0\x00\x0b\x08\x10\x00\x08\xd6\x01\x01\x11\x00';self.assertEqual(jpeg_size(jpeg),(2262,4096));self.assertIsNone(jpeg_size(jpeg[:13]));self.assertRaises(ValueError,jpeg_size,b'<html>')
if __name__=='__main__':unittest.main()
