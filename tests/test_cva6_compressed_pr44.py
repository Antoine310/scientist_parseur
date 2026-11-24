from collections import Counter
import pytest
from rtlprep.cva6_compressed_reference import FAMILIES, encode, expected
from scripts.run_cva6_compressed_oracle import MUTATIONS, mutate_decoder, _oracle_failure_evidence

@pytest.mark.parametrize("family,counts", [
    ("addi", {"valid":1953,"hint":94,"nop":1}),
    ("addi4spn", {"valid":2040,"reserved":8}),
    ("lw", {"valid":2048}), ("sw", {"valid":2048}),
])
def test_exhaustive_classes(family, counts):
    words = [encode(family,p) for p in range(2048)]
    assert len(set(words)) == 2048
    assert Counter(expected(w).classification for w in words) == counts
    for w in words:
        assert expected(w) == expected(w | 0xFFFF0000)

@pytest.mark.parametrize("word,result", [
    (0x0001,0x00000013), (0x0085,0x00108093),
    (0x1081,0xFE008093), (0x0040,0x00410413),
    (0x4000,0x00042403), (0x4040,0x00442403),
    (0xC000,0x00842023), (0xC040,0x00842223),
])
def test_known_words(word,result):
    assert expected(word).instruction == result

def test_reserved():
    assert expected(0).illegal == 1
    assert expected(0).instruction is None

@pytest.mark.parametrize("family", MUTATIONS)
def test_mutation_guard(family):
    label, old, new, mask = MUTATIONS[family]
    source = f"prefix\n          riscv::{label}: begin\n            {old}\n          end\nsuffix"
    assert mutate_decoder(source,family) == source.replace(old,new)
    with pytest.raises(ValueError):
        mutate_decoder(source + source,family)
    with pytest.raises(ValueError):
        mutate_decoder(source.replace(old,"missing"),family)

@pytest.mark.parametrize("family", MUTATIONS)
def test_failure_evidence(tmp_path,family):
    from xml.etree.ElementTree import Element, SubElement, ElementTree
    word = next(encode(family,p) for p in range(2048) if expected(encode(family,p)).classification == "valid")
    want = expected(word).instruction
    mask = MUTATIONS[family][3]
    root = Element("testsuite")
    case = SubElement(root,"testcase")
    failure = SubElement(case,"failure")
    failure.text = f"PR44_VALUE_MISMATCH family={family} class=valid input=0x{word:08x} expected=0x{want:08x} actual=0x{want ^ mask:08x} xor=0x{mask:08x}"
    xml = tmp_path / "result.xml"
    ElementTree(root).write(xml)
    assert _oracle_failure_evidence(xml,family)
    failure.text = failure.text.replace("class=valid","class=hint")
    ElementTree(root).write(xml)
    assert not _oracle_failure_evidence(xml,family)
