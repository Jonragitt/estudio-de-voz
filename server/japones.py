"""Lectura de palabras japonesas (rōmaji) para un narrador en español.

En español la «h» japonesa suena como «j» (Hokusai → Jokusai), la «j» como «y» (Meiji → Meiyi),
«ge/gi» deben ser «gue/gui» (Genji → Guenyi) y «ky/ry» se leen «ki/ri» (Kyūshū → Kiushu).
Se aplica a toda palabra con vocal larga (ā, ō, ū…), que siempre es japonesa, y a la lista NOMBRES.
"""
import re

LARGAS = "āēīōūĀĒĪŌŪâêîôû"

# Nombres japoneses sin vocal larga que aparecen en APUNTY (ampliable).
NOMBRES = set("""
Aizu Akamatsu Ashigaru Ashikaga Azuchi Bakumatsu Bishamonten Biwa Boshin Bushi Butsu Chihaya Chikamatsu
Daigongen Dazaifu Dejima Echizen Eihei Enryaku Ezo Fuji Fujiwara Fukagawa Fushimi Genji Genmei Genna
Genpaku Genpei Genroku Gifu Gion Hachiman Hagakure Hagi Haikai Hakata Hakodate Hana Haniwa Hara Harunobu
Hasekura Hashiba Hata Hatakeyama Heian Heiji Heike Hibiya Hideaki Hidetada Hideyori Hideyoshi Hiei
Higashiyama Hikone Himeji Himiko Hino Hinomaru Hirado Hiraizumi Hirobumi Hirohito Hiroshige Hisamitsu
Hishikawa Hitotsubashi Hokusai Hongan Hosokawa Ichikawa Iemitsu Ihara Imagawa Ishida Ishiyama Iwakura
Iwami Izanagi Izanami Izu Izumo Jinshin Kagoshima Kamikaze Kanagawa Katsu Katsuie Katsumoto Katsushika
Katsuyori Kawachi Kawanakajima Kazunomiya Kenshin Kitagawa Kobayakawa Kojiki Kujikata Masahiro
Masashige Matsudaira Matsukura Matsumae Matsuo Matsurigoto Meiji Michizane Minatogawa Mitsuhide Mitsui
Mitsunari Mitsusuke Mizuno Monzaemon Mototsune Mutsuhito Nagashima Nagashino Namamugi Naruhito Nenbutsu
Nihon Nihonbashi Ninigi Nobushige Odawara Okehazama Owari Reiwa Renge Rennyo Rinzai Rokuhara Rushana
Satsuma Sawara Sekigahara Sharaku Shiba Shikanoshima Shiki Shikibu Shikimoku Shikoku Shimabara Shimazu
Shimoda Shimonoseki Shinano Shingen Shingon Shinkansen Shinpan Shinran Shinsaku Shinsho Shirakawa
Shizuoka Shoki Shugo Sonezaki Sonjuku Sugawara Sugita Sushun Suzaku Suzuki Tadayoshi Takahashi Takashima
Takasugi Takatoshi Takauji Takayoshi Takezaki Tanegashima Teishi Tenjin Tokugawa Toshiie Tsunenaga
Tsurayuki Tsuruga Tsurugaoka Tsushima Uesugi Uji Utagawa Uzume Wabi Yamashiro Yamazaki Yokohama Yoshiaki
Yoshida Yoshifusa Yoshihisa Yoshimasa Yoshimi Yoshimitsu Yoshimoto Yoshimune Yoshinaka Yoshino
Yoshinobu Yoshinogari Yoshinori Yoshisada Yoshitoki Yoshitomo Yoshitsune Yoshiwara Zeami Zenkunen
akusho aware bakuhan bunkokuhō bushin daijin daishō emishi gawara giri gosho haiku hanami hanzei hatamoto
hinin hiragana hosomichi kanji kirishitan kotohajime nanbanjin nishiki rakuza rangakusha shamisen
shikantaza shinkei tetsuhau tozama tsuchi uchikowashi wagoto waka wakashū wakizashi zukuri
""".lower().split())


def leer(palabra: str) -> str:
    """Pasa una palabra en rōmaji a cómo se lee en español."""
    p = palabra.lower()
    for a, b in zip("āēīōūâêîôû", "aeiouaeiou"):
        p = p.replace(a, b)
    p = re.sub(r"(?<![sc])h", "j", p.replace("j", "y"))
    p = re.sub(r"g(?=[ei])", "gu", p)
    p = re.sub(r"([kptsc])\1", r"\1", p)  # Hokkaidō → Jokaido
    p = re.sub(r"([kr])y(?=[aeiou])", r"\1i", p)
    return p[:1].upper() + p[1:] if palabra[:1].isupper() else p


def aplicar(texto: str) -> str:
    def rep(m):
        w = m.group(0)
        return leer(w) if any(c in LARGAS for c in w) or w.lower() in NOMBRES else w
    return re.sub(r"[A-Za-zÀ-ÿĀ-ž]+", rep, texto)
