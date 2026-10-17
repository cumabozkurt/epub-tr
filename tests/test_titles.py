from epub_tr.titles import short_title, volume


def test_volume_forms():
    assert volume("Oliver Twist, Vol. 2 (of 3)") == "Cilt 2"
    assert volume("The History of Don Quixote, Volume 2, Part 34") == "Cilt 2, Kısım 34"
    assert volume("Pride and Prejudice") is None


def test_short_title_drops_subtitles_and_edition_words():
    assert short_title("Gezgin Yahudi - Tamamlandı", "The Wandering Jew — Complete") == "Gezgin Yahudi"
    assert short_title("Mary Anerley: Bir Yorkshire Hikayesi", "Mary Anerley: A Yorkshire Tale") == "Mary Anerley"
    assert short_title("Ayakçı Çocuk; veya Phil Brent Başarıyı Nasıl Kazandı?", "") == "Ayakçı Çocuk"
    assert short_title("Kriz - Cilt 07", "The Crisis — Volume 07") == "Kriz - Cilt 7"
    assert short_title("Marcus Ordeyne'in Ahlakı: Bir Roman", "The Morals of Marcus Ordeyne: A Novel") == "Marcus Ordeyne'in Ahlakı"


def test_keeps_plain_titles():
    assert short_title("Suç ve Ceza", "Crime and Punishment") == "Suç ve Ceza"
    assert short_title("Dr. Jekyll ile Bay Hyde", "The Strange Case of Dr. Jekyll and Mr. Hyde") == "Dr. Jekyll ile Bay Hyde"
