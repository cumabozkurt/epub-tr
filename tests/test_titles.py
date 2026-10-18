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


def test_tidy_brackets_editions_volumes():
    from epub_tr.titles import tidy
    assert tidy("William Shakespeare'in Eserleri [Cambridge Baskısı] [ - Cilt 7") == "William Shakespeare'in Eserleri - Cilt 7"
    assert tidy("Fırtına [Cambridge Baskısı] [9 Cilt.]") == "Fırtına"
    assert tidy("İç Savaşın Askeri Anıları, Cilt 1 - Cilt 1") == "İç Savaşın Askeri Anıları - Cilt 1"
    assert tidy("Margot Asquith, Bir Otobiyografi - İki Cilt Bir Arada") == "Margot Asquith, Bir Otobiyografi"
    assert tidy("Leo Tolstoy'un Günlüğü (İlk") == "Leo Tolstoy'un Günlüğü"
    assert tidy("Devlet Adamı (diyalog)") == "Devlet Adamı"
    assert tidy("Ecce Homo Bütün Eserleri, On Yedinci Cilt") == "Ecce Homo"
    assert tidy("Artemus Ward'ın Tüm Eserleri - Kısım 3") == "Artemus Ward'ın Tüm Eserleri - Kısım 3"
    assert tidy("Hacker Baskını") == "Hacker Baskını"
    assert tidy("Don Kişot  -  Cilt 2, Kısım 3.") == "Don Kişot - Cilt 2, Kısım 3"


def test_tidy_suffix_typo_length():
    from epub_tr.titles import tidy
    assert tidy("İnsanca, Pek lnsanca") == "İnsanca, Pek İnsanca"
    assert tidy("Frankenstein (Shelley)") == "Frankenstein"
    assert tidy("Arthur Schopenhauer'in Denemeleri (10739)") == "Arthur Schopenhauer'in Denemeleri"
    assert tidy("Zeta(3)'ün Değeri") == "Zeta(3)'ün Değeri"
    long = "Brig'in Hayatının Bir Taslağı. General Francis Marion ve Tugayının Tarihi Hakkında Uzun Bir Alt Başlık"
    assert tidy(long) == "Brig'in Hayatının Bir Taslağı"
    assert tidy("Kral Lear (Shakespeare) - Cilt 2") == "Kral Lear - Cilt 2"


def test_tidy_turkish_letters():
    from epub_tr.titles import tidy
    assert tidy("Jeláléddín Díván'ından Bahar Şenliği") == "Jelaleddin Divan'ından Bahar Şenliği"
    assert tidy("Âşık Ömer ve Bouvard ile Pécuchet") == "Âşık Ömer ve Bouvard ile Pecuchet"
