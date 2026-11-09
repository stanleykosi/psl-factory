import gzip,json,tempfile,unittest
from pathlib import Path
from scripts.impact804_index import write_index,read_index,equal_index
class IndexEncodingTests(unittest.TestCase):
    def test_binary_roundtrip_deterministic_and_no_overwrite(self):
        raw=b'100644 blob\tpath\xff\x00\n'+bytes(range(256))*32
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/'a.gz';b=Path(root)/'b.gz';write_index(a,raw);write_index(b,raw)
            self.assertEqual(a.read_bytes(),b.read_bytes());self.assertEqual(read_index(a),raw);equal_index(a,raw)
            with self.assertRaises(RuntimeError):write_index(a,raw)
    def test_corruption_and_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/'a.gz';write_index(a,b'original\n')
            with self.assertRaises(RuntimeError):equal_index(a,b'different\n')
            a.write_bytes(gzip.compress(b'changed\n',mtime=0))
            with self.assertRaises(RuntimeError):read_index(a)
            a.write_bytes(b'broken')
            with self.assertRaises((OSError,EOFError)):read_index(a)
            a.write_bytes(gzip.compress(b'original\n',mtime=0));Path(str(a)+'.json').write_text(json.dumps({'sha256':'0'*64,'bytes':9}))
            with self.assertRaises(RuntimeError):read_index(a)
