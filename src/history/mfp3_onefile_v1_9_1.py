#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 ONE FILE v1.9.1 — AUTONOMOUS EVENT LEARNING
================================================

Un solo archivo para:
- ejecutar el sistema v1.8 (que ya incorpora v1.7-FROZEN + Forward Paper + eventos);
- enriquecer noticias con categoría, novedad y decaimiento temporal;
- detectar régimen de mercado;
- aprender impactos de eventos por categoría/régimen;
- verificar salud de fuentes y archivos;
- crear backups diarios;
- instalar/desinstalar una tarea automática de Windows.

Uso:
    py mfp3_onefile_v1_9.py
    py mfp3_onefile_v1_9.py --install
    py mfp3_onefile_v1_9.py --uninstall
    py mfp3_onefile_v1_9.py --health
    py mfp3_onefile_v1_9.py --status
    py mfp3_onefile_v1_9.py --full

No ejecuta operaciones reales.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import traceback
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

V18_B64 = """eNqEu9eutEyXJnj+XcU71SdTQ1eReOhSH+AhsYkHtVTCe++5+uGr6r+npZFmUlt7Q7AIIlaseExm7v/yf4D7uoBJPYD5cPyZ7q0aB+Sv//LnX/6vf/mTjlk9lP/tz74V/0L+3fLXP/3TP/2lCea/IH8Mnf8jyCr/54D+lfzrv/+/X3/95ep/bEM1/tAWK8me8cekLfqPY3DGH179Y8u2w2v0v75h6/gnq+OlHv/bX3/e13T/6YsJ+fdxyIu6y//9gP6d/Nfp/usvY0rrt3H9/wz78y//Uuxd9/8Tsm7xtq9//SXswz/6hP75T5xue9zVT/z3pIh/ESwj4vU/a/2nitP8TxF3W/xvf8H/e5wwLme8ZH/MeMqXf/sL+ec/S56OXZ5u8Z9h3Oq0jtc/95vIYcuvbfzTx+kygn2+pHE2/ttf6D//ybd63vP/PfwNfnvZxmUY1z/Fvu3L+zf+A/3XP9jbFfz5s+brf4z53/7C/vlPmQ/5Er83TOOy5X/fvI5dnb3dv6nVxz95k6f72/34DjD+z7m+wXGXr//6H6v5V7GM/Z9///f/eFD+7//+p+7/7ulPPLwDirf3hjdN/2hbyile1vwf50m85jj6j7N0Pf5xWMVr1dXJP06bdRz+cby9o8iTOG3/0fD8Hfgfg8ji7c1Gn/9jCP84/69//v79vEP/z6P/jJ7i7e9n/CPYfE//88J2T2/V/qOdq9Ptv/5R63X7X9MY9v4tgjfTw/SPpikesrfh/Zmyv/7alvs/a+x/Xr2LeoiHtwT+Xszir/xK82n7I//HRX5ZxuU/o5e4XvM/9r1uec9f9fZ//kfr369/+h+D8Hf1/K+e/vUP/z/XZR/iP++KvSWXP//tfwz/9P/c8x/1+y/vROvpTz28Fdt1/+v+fwT+819/eRDx7wyO/vnvf97lzPVFL9INRj/xjX6xoozFAYbZaGxrzwuixdHAH98FwuqhvZKspFaTBiPTdsAyNI0zOZRMw7bAqQZqXEa1qgouH6InFgeI1G+t3sOP7nZvBkwH69rfrw4w0WoLSbl5EPgA8XxzhYkiv8eegRTzIayP3UPESFS8SXhgaRUFrfqCeo9EPwfp9g3snzB3ZKbeoXhJMUV3CB4mPJDRkSgIZiBYgUPKlVnCnBoDGM0nE5YIKT+ihQHpw6yUBKoFiohkMZh8ZidCit4NpZXBMX097gfjB7ZQ3GKE306KraZzphG7whz8YoMDigGExoAhwXT3JJFzmVy/U5pZIKLYAh2qMTAglXAK/Kb56dSi9uSB5M0CKLggshJ0SCP/etoN1O/vB+l9FTxL8OAQQeFUL0eJMHdQCURFqdgulL8llDStj88duSGvoPUsSswXrsR6xriPFJcrityz2nokXFowZtOoigDyUXQSB37S0cW7dlziQPXxsDADU3JJVfDzeVS6E4UwZAIpj5NnNQxtDDQB+YJiZrIbtlyRJZrbJDodlhnoUFQTX8rCiMYZgA5PH2jRD/PAZ5Zr1dnNp1m0APzdFEuIk6zu8qxoBdjAekneWMl+q24H6YwFaK7k1k9NKQjSfmd+4AzTUkXJyIeYVAD9OyVSnvLhCYcQYv++E9O1xU8X5TqRFDLQ3M6ja+7N3ax9aIhTVF4JtYhkPiAbs01pVoHkp4iNruNxfs/iCsRSXc0DXIwtAkgYZbHdTB5eF93rFD6ElcSBq+q1ZWa0Eio4RxlYTjB2XFxWmmL3dLZBfTUzO+PlPDBgm8nWU/HnVylQRftFO0d8vHUoAdwzMtqQOVZXh7MdeLxJc/lY0x1r4IOGf7a9yyqMnrtY9GMLNK3ibWzGsQz1VSpZp52OwpVOFOOrhH60yHfcgXA25H8x/LIYkEV3HVPlBzKHrMTQ6upbKvNDjBpY0jnrnWweiamUbsqNAQ9PwHY/7vOLQX0wrShWiHMHD8YpaO8zZepWZqlEArxUC2fwaU5Tts6rZn3fAYSbNFNxxnkP20mnIoGMKE0YTk/GgYbY6KjSM+GW+FDuXft2AJvMOfDHVdNkCtYIZ82mllwtAAjrlUsXaMAUr3/Ej/r9WIf19IZH9788AwLeMTA1HEcyOL81luXjAuoBpVCwoBRe52B49rmVqMfw/DPnTMn2eMZZ1XbIzsSok8p3nUirIQqOG6JzfpZeVIw5H52fqppEXF5XV9S5HVlkijOsKP/XSbs8EE1uPV2SpzpqnNCnUn7ok0XMaLvB3CDRBP2geHZ1lyg1tBMp7WQdQ3bNBRKq2dHOH3CzcDlza2IxhV2VbDcbgIYeKodz7vnmXm4rUEvznfd2WaG+7K7o9YOeph7QweEzAxrTNKklW3esN0ZHqJW1mcMV0PbLE5u3F8GsZ7q/TaaMXZL1OQ8bb2ncGsN8KWEHjBZG0dWFe4QlNM6nmAf8OTBxfQpipArT64XGqGpQatHB2SjMwR0XNHCCwEbCOfRR09ukULPIasX4m7XCqnp9f/JaRpHlaWDdwDs1nBPflD/N9Z2HRBFNyxb0LosdHbdsCxwHAXC7m3vxrQPI3m0ZrPJ12Dq0wvCnor7g2gIM06BMM64ECzIEQ+O1qa/u9DvKhaA3QGPkki9M+QIjDoAlFmmQE7H5b5FIJwEZ6OkAzctSF2B8M0QmRReSkJOqIDFb6a/hSLBUJD9cqsD6ApGYl2Aqp8DiIkF3LxqVxlPelTA4H3ZOwumcLUCzweGogUpOJHhI2inSuCDmIiGwjAjjWh6SDTZAik5kbbk0atqM4wpxaPFPwYcZsdxZMi6BY8fkIh0xju4DkIogSInV8atBOMqycjOtlkKqD61TSAO5W06hCAqYjLTAOdgwJEAiSx3deHmZR67WBHZ9cumDFJLALDuxDy2pMxl8IKjJeAS5NvosuXhmXvSPaNf6Dq6U6LHq6SfPcO0kVuqnI59CUZ/wSAOIsEVw8dlwXsBrlsAiEySd4GA2o1NPPzj0Fy9ivcAIDH1yhDE/nBdzd5R32ltzZ/GzFQ6Cjgypcp04U0k+6UKyQCsknfAm4wQFpbG4zgINgSfYjigpzXWRBBTlkaKRc0cnUykH7RmmhjxujpO6AqDI/O7AQFMcEYu3OBrVuESKbm06Kiyl1fOIiYDIVLBJTcYHAAnNG6jHW6Tnb9FFmoR4uUhf0MiRk5zMpN9bJudIZIQp8se+IXlW6mAevwN7EF9rXNHzYcT4cURBD1Qi32+9nAbT5sQPBlEw4Ej5csJkebD0J9vwQN/9Qs8HfGnNByATuEdlNcNkumERULo4sAJEYkSl6tkki8JLgWOxPEtkuc6dljJWd0fFZNGv4ME+6+Z/E6Yi8AW5Cv0e15f/sd6wiJ27C+0aHzYeqRLKQGNEZIHaHuNbammg+kUT3zmfRNcxNzQA/DDGJyuspSyE9tdtaw9zsC0FSZ6OosXAQGSEyWmvZokD++kxXfuyIg8SUkrYh/pBNEjW3QMo9kMV1nEPftBUCFJVRAdIcOLOnKiYGeZ25JHPzddADzkoRATEPxiJB14rLOxBltJH2b4KgIIRLaxQMvy4lo8YP3DCGK8AcrDzKCBGHkZ7R+WaBNfglIsLaRSx6rpHmm2WllyFw+iOxKdqZjga5ScJKw5MBPn7EmvazzE+zKFT3zaNLVKzDAfNYLNnku2U7p6O1Sl9eeJe1mRnsIxVjwIwTWhxlYVHEodfN9sZkNJue2qbqSL/raqJ0alxGE9BsJKz6n8uu1YOt54M0fwO84NX5iB8+QyYxUfpGF2e2jwSG/Lh25Qij5EurXTqQVJyf4oEW4Wq7QMbL/0IlpoAfmDqC+nnL7458JmGK90pmUf8mJ97XB0nXE5+3oGODuxZWgzEIrmKo+FvUa5AO3tQ3WNJmuaAFFTLZmHev5k2LRLUrl1Oejb/0SE9F0zWqeuZi7Kc4zRLGAVAzz+CKuPTyxNeNm3EeKvzooPvw9JLePmZzG9+ff1a60cDAet1Jv3dMDzuRN6xq3QIZG4N3Lztxi/dIZNfLDJXkKzHnyoildKqiNzC5eVlm5z9hAhrtYL3uWqmdw3phjqv+4XnbR/ZbCPZzk4pU+YVwV8ZBTP1pINQPkNTw0e9pwlBBwO1DzFZzttbSY/Z/RF+jU8YmchI31fPRXnMTpbvk7XwAOPmTsSHERmUx47xSGWKkf3lTK0L2nuHtZKS/aVRx696xJRByEoKyvd7/w72Z/BaSM0VTpSuzeGnPprFzy8OdFc6uGYpB1wN/JVX/KPXNOyIVz774Xel/eAmXSXESEz/KS11RJodUJv1mSgNF4vWxrMLHib9yGv54B6WUGLQqIpo6p8HCmhnLiJ0WBo9cKZsQy0ZUij0QXbyA0CoLGkkoRwXe0BXBzKd2VQPvtcEDz5dGkXhV6uaeDX3vq7MBJRXKrANAtz0a5h7YPLyX8fmXTUKL9KW0c2c+0mBKfdVEOnOudQD3Er353zA+1miXhl0irSgSxnzhHtsMZoxatR3peTvAzaNbxfaensyHUPGJtS+9yrBCi467juqCg786H6a55W9lPgkp1rk5gMHELO/d6nIBfRZ4TRxzywotx23xO+21PNo7xr45XeMQLRehQZ48be3qCSPmQGsfs6IkMXKqD45MZK8kZlGTkhbS8PbHMhipIXJh/ZG1G/y1e+35aLnCtpr4PY7xlmAqxtYb/76V0gwYt+uIy3p7oWlH56cyft3Dkw6gesXcDZ7rn5OoHPWMK9Hyca1C739f9vlemUu8nyLzZlrKv7UReev/jUtv6YMY+5HsZ/9g2qHTaRQa7YmnKU8lHsMMdsKaK9c1z32lc1EaoJqYAA/qA5fPTjLSrsO9OrnWZxtxVte0eDBTOsPunvGB95HqV6IBTfFpYiy3XONO8Tvwse92bo25TqOhi5NwzoR863lf73Y+DDkM24v4cCwFVl4u7i52IgrYwAXLYJhJyEMO3dzvfmCHmhIwIq4+Y6hdwXSCaoyxQ4Y8U5vuLW5c9Bth5342TvzGrthnmzKcUK+wJ4iM+/6ECBRLXtX9c06o4WGtwVTfSasq60r34W9tGl20GkOsgkjNI4wGfxQRjkOO+1N5dB9HsxcrsdjJTizot0dHoGmPp1hgyrxDLMCu2tMA9ucMgv9Q3b5dQ3keiznDJklCGJYxYclJXgre9LjPW/xFF6fPSCZx80R4EtrREoER/55UXWZfmhhna1DuFgs4WIv0zYynnV5E5rXeb2l5U6D/D6GltLHoABZ52Gvp0Qf8xhieN8S7pBN3KK3PHN2Ksk1T9DLtlDkfBqFjbRGNFobrORU11GVttXLCYESY5R01o7j7Zj9K7iXlIyyERjSDbIajIbLX+h305FaJIuUDZC0wkuAKI9+rQHoy7Tqfe1cRdD7RErj6KYw9kXFCk6y+zdLhoxqc+1lYX5OUJw+X8wwmK3LqGVk5mcN5rvDjV6fGyeSWFw3wDkEfe1kjYBRs08RiheehX7Pr6I3zpeKT0BMSWJeNZnMRqCOFD3xDWlgVDun7+VTZ6qIZ3pwXdm2rKxACxVa2KF47AlL5sUq/yC3sM1IF446oV4bw4AXG390pEdjJ0Kb+ROtCe389IVuWZhmsvQjxND1C1Zp5bvPbBM0u7C/KvTs4A4tzVyMSvcWxU8tvBnk37u8YXNentQRIW5+MTPTSTNLsBWKAof1t5/TtV5KkjZIqvJnj+HN6bjwkIcXUkkzZhQI6VaBaJGrXAHvdpjsfLk8Igl1kRsLBx7GLC1cMYxBcDDduM55/VDtTTnEt9JUB6MFbi6Iy07wNBOGmr8OcJeC30RPqTo8Cu8O37n+3c+plAp4FYMEVzHGJDMyHGusSoqdsdKoBJwkg7lql2FQfsl+W6FLODmvotaqRB4JT1tzIeA2Yfw8ArFxNxD+aiDj12134pVrhKDI42XgZK5JngzYQbUxiwSLkR2aNrCIrjMyQ4wxKNrYa13P4YhWiBNxYgvDePgAKWyRxjQXDeoYqha01k7Gcap/AQLRKwiWTPj7u184EMmnHV7efHl9M1rNUnWy30fiKRJ3sOTHQyOsrHcfOlHG/zG0cpR3/NC6DbC5ixcMkSXVtg0zu4v3t1moTUDKCdSJVt8Aei31mLwuyKkcT/Tl5gGMsOKvEJnj8vsNlkN4ZoQDP+gevBzLBwo7oyn1ndY2N1roEwx2tjHEpzpmfN+G7/q4/BVJAGj15usSfdAg5MTeXs/pU3tdBb4XwP53/l7iSFLya++ipOU+0sdeMhd5hW1CcITuemyeLdqu4yur7maKdbZWM7ZFNVME9eK1r1xcniDjbXhseR/WmcohUUq/meteDIl3jD+CvuUtEh8gPuRTx8zDgslPMc26vskUZ1k/ccXZsL1d1YO/LP9L8NvohsMEeHS06KYjRMtKRNEyQruYjHFczQNVRNajjtsClrEL1iDXLqNJT6vUB1FZbX3QpKXmX6kMK+3YW9P3Llsah/c52T+Nh9IV03A/1opfcM6gXRN4VkYABpIB7yeF5ClwOIXh6+vSViEcna3ifWZ5EZzHGyl6H+T7RVsIpxAJc2NhiiJHRvgbqz4jM1ncTcth6++mt27ypfpFfZ+cvuqphzdZ+YmpGzU95Oup+IHxMbzz1zIMG3BnR8cmpgGgDI1Man6jbheJydg9utpj6+Cx+vWj6Qh9jlvcrCL/sKy/MPXL3jcMDvnriKSyKuMMdjWGYiDxTp4onklOrk4IjSlpRE46HQiOVoSYdgLnERHb9JhmovApdfWzvPZB5jWcdWms3nRv+v44lE0A9DImx06QSHf073B4sz5eV+LMJDQ+G4H3G2OtaqF8q6CfB09hKSO3xohcQmJK69fQn35p3GjcIUdyLUkBU2nCLc8OLZ+u/nivrg4Rq7tqSHXzT+xyLP7rww/6NeM+gXigGH0tDNJVyuu65ZdJ6aKKndqd+NLXU3gMJ0fQCi19klqr2biEtRN62DPgh3Y0tZiqBvCJiKD1Viz2/j5XWZrWVXn4WQVYQT98JWWcX83RoQ5pzkvQX9588WnsFaMNUoY7R/3FoYoAsMo+Pmw2SWou4LgZwrgVAOUJkNOhFPqJOrHc2OPiuhwSrZSjM2KoSPvSfjx2Hp/YEi9ATZ70ioek+YK3EKBCk2KHhVEGgREcZ6OHXvWt+LzuGaXGn1PYQW8tMV7nACsfOboRJ1PjNYxVO3d1h+ByubT5kcmyzbluSKBufb1wn3h7NwrTwLauoe/2JC6+FyDCii47s+uFrmak12u8MaRHDYqzMrFNXwBjHNKSLdiKJL+MNzYsabqIIKC06qHA5H9YS++g+16ISkmgdZbP8DOjEomEYF8DpQorwcoMP1yGBIMhEzJgRrI22THKIcvwendPA4bXpz0MQ2o7ctdbAx/5ZF+KCaSl98H0FTxxvtVqD5HnVUdscnD4JNMVy9jcTIGb+m3BtxJNakmy+J5y+pMfqqIWsH03dhnDYRJ+9ldIQPStdKFLW/L81TPvCgv96P3754hHN1NEad40MkR7ydtB2F4h/7mVoMXZSPZqYW8NAPJ/wT72kc1a1HZh8w188qGECjDCm+JiprE5J5UC3wUt5Y3hGXyTuC/z+cJoFhjDZgClrTrE3qAxVzNxlF35WpgxQNDf6Hll6M2z4mPJ22ct0ezX2nFb2DA2Ly5t/g5KevqIzCrYiTMWHIJEiRUWPSZdCA9BELm2qsLtus9qNntEN/KhnrEmrkp/7Knt+7FvgjNujBmtWV7XsBO3u6pkw36SZ/LN00NPN/8hlpLCXhrAQWA2jd25DymxTwWk9si2fBoPG7mzPcFW1R5BghRiiPSzVh09Dr4mbeS3fjDeUTevV7y9uNFZEF5VaoRAjx7zWyKufnuNYl+4UBFCk3ih5su5QiCnDKW7+QNfCUCim8MCBUOC18BOyLFjDyNYzRdppLyb0hG94nH5FtTP66Gp2P3ZBdMUvR6GEBkZtneEltrveLNIyE+pspLZNgx8ASLBGPJ0tXzZj6pv8KvozE83s8y9W2p15HQ7XxFeb0UVEho8CoZfwruPOWngebwEEv33g/4s5GVR24XtM8MATR2aB1xSe9bo+Qq3+ivcn7kk2HyMWEJuBarPo6USbZc05PitfRpPlIJM5I1Wca3dxCPV+q2VT5uPoMxylnXAzxKBHtVs77IKqK8DTbBqsvsJU47PosEnrjcynDu6B7hk3YMBoQmXTu6vdrXZUL0+EfATL64MObgeoDbEZT1+oCa1TVEBuXSi5nfOpXUpTlKycrOmzG94ShXxbrgxNon07FTkxl75es/mpmz2opJ2Q6Ck6Zv3q+yAUuqhQOo/FSSfh96MwmTWczrwWPa4dZ1CWuZDr7AN7XtG0OgkucFqncPS+/MzUpUuS8reApMlYwI0CZvax+0EEdknEaXbKj8d9Vs5rQTnqqzHAMQb/gWDAWCnpuuuOfzaSDw+Bt8kS5UKXxzv60+wPGmwgdGsX72rgb7rSq0DPGMLMbH+uAVCfgzG533oEfNjYtX5Ld9TYLpXOXScjzKL9rtrdw04VwuLHmTvVGc+PRIuDszR4hpLBEXGDlJEO5fozb0mwwPg5aGfQdnnT7T4ZuXdpDFa+/iI67fa6TtJwsKXoSDWphXpupy4juWpLWNVdM4AQe5QwqgIzBl5duukvz6ixSV4nXrtSbpEAH2EhJQRKO/4fd0OpwgkeEvB5sic9Efuf4xSxfbmYG6Z4+qkQsqguLaEWpmNOnNR8sl0CB7caOqZB8mPIaO0XyCDgsXay45pa9hqdTiVoMTj+al06nJmDv39pmkHKdzEKCuEQI4WMmR+WJBRpoh4f57PA7u/56rLmsTrWQEcrnghZ9akdIuh2grZruGMMqm8mXY5L8QR7zaETB8MD0Oalgasv98fboF1Wt6oLXCL6/KDKAGVhxJfF8hvRoSsFD8OBDC2Fw/9ipN/CKR6DvB81Z3huNIz73LdQCTtEGdNXvfiBD5qzJow+x2IbP2UXfgi/Ob1q8oDmAdotoa2uemUpCLSOd8LVGcpMS93b+cNNWAfDxzBgiRBtaecHPyQP7IwXuURMjZ+x9LTCRxn4TCXvBeTMwedEgnKSRXrGAMwa0KUaYrPA36hykP34pJyN8VVcM2+pEcVuX4NgOP/mjSPiMyy+6wSSwj/is8N6Woq79iP676He7/7jHlmAWCDcYuTj5HOdrmvt9NCpdervM1J59rwmIfPz08E41gOxIBrb+i2oRdMRousZbTeov13hxwpfZ7no98SC8qxaD8QH+15xj12Dphj4gUqh/4OC/RW2h8TXLwD1d7nZRWsPKwzuPBfdYGpl+wMoc+6GNGjia+UO+6JsxxaI29cVC6lBVOVnf2wARWrXrmAkgZKoicbW6ymkF5WDno4/E3usZN4yXPiswPXu6VEX/IlglIiCQjmr34KNpdFz2DUiLtmQ489pFehefK3ctXPK5iUWBdS9vsJHpY3dbEAW2qAVk7xVvB7RkQvj16Q11c/ikqbOIUAS7ja1rNTD0nHUqp0H/M1tVG5PzFir2q5pcrc/sia0JdeQGydn8vUhSWR4PXrGtk3DXOJXDKa0vMzGZSP14TfSVttZ4gfNasg8JEHIuzMXTBCVzAdAY+9GUkS0cOL1WUDmuWXw2da4qJbcmWFacvzOoy7PceO8m85BtIlzmv7KkHcc5gpQcrdQCMb49INo3MvPxfOgLI+9FW+fhXxJlUoooWiNwECvEMIE6butQh03lmfh7UStaMSx8haTu8zb9LRGcUvO1VG3BcikycvjDGyMXHTUXgU7nzo7IcZYUtwZ75WbCA9vwDGpVjMdl2ssCkFZVhFUdLZ1i8nbwvnbhsECtHpN0fMaWiOcg3tIwUcX4ZMxbC1KJd+KAZsJN7TjVNCHa98DZKng9TklKa24n5+ohGQZ1kkiqqSkewQF3NzFKGyxpONyvSwfFILKCYvEcc7pPRarsa0GusbD0kHJypi2Ultxh22067xrI1deHl3HjC3e9g8SxARruV1SsMDNUrQCDO0Hcqj6jjRbtzfEugxRZriu1H3/jN+IfArjrlMGFd2ueKxRYDNhnZEONnbGyl/4IfOlVt4HTu9MA5Ud54tbvEm3IDPfmCKd4IvQQf1L85C9XdBO9H9eH9YZbpg0A+DoUpoOFzfaMpr3UWZqkl5niVEcz9VRABox1Ps74Xx2Q3EryxV7gucu8vp7Tz1r68VpYhZbR8RO0MkdFN0aFiTjpvORMGukbxHpn2EKNvaq7n/+rwr7D4Rk3Wmo9fE4y0RnsYjBixxbXti141rVbUveMj6JJc7NyAmRvP9DBOLa4WBfOZ3ZAld9b7qVRM9O1JmRYJ9II/aE9P6BsCaokolZVQP4IzppHHhttc9RcK14eJcaDfwATH13PW9FMfrVeejdxy5dxfhL3l1Mw9N/jBLVFsywlwNMFpN1D7zljXvCfa3+L6PxoOBBYavxIoa4QA+YdTTSc10CWOx6qEXztSxWg1XmZkASoI0p3CuwMQ1L7EabUNTSw8LU76PgVl8tRzBsmseV3Dl5sfCysZksGYtQt9lU/73Te8Eo1NH03Znx4frCe2Oy2kBQJezI3n4aID6DjevHrnMZlM0IxO2rbvfj8ZyeKrYhCrafLrIohh4vG/WUaaWZ6m2MhdDnOQbpKRsCVH0iQAxDo0ngosldifQlnf6NHbJPPqq/D19aBR2onUbonxTk7mPxe0sHhSPoUTwrtg4oFOoQSL0O/juxLnpazkk0o5Ji4BkTtdXToDOg5E5bdn9ih90cfx7dpOxbnBUvHqpqyl5d+RgOlLp9s3MlXuwv7gX4ta5P7canJ59mINK6BbXC0Iy8PWiO3VJjFE1aqyHpB6QCqn9aZ/00+ix+kMEddQof5zVdvU9e9DbT7+pVy52zld8HTz0zTdCOW04blrI1RbJh3ncpSmTITkpbHH+0cTuhQ3RUUudHJy7hL+dLwARoyklj5+n0yG0pazKFnq6W1kBTA1lq6iZMthIBCY/fAKYythnH0szMKuqQ4tuaB29Sh74SyqIF3ECtO4nn1l8Rf7xV+3RtOdZnNcRv4F3QlNhitD2pkn/uoK6RyW5XZ+vI1XNFw6FhGj0TCu7TKWZz7mtnegQ16lAyoTHnr42VZnI94ZNmdex36AI8RsW1hibdYjIp7tvXzN325ZIQGYMjaYTMXDu2RyVhlJn+xKfPXi+fiCo3e58NBB17kwsl1SDJV75Hx8MWg1UmixslhcEtknKAdkKWJgOHs5aOZdQkuitdMtKOC9JsNRyxXl33QbOQUQbdFfbNpNNzfvfayt+g+KzIwkb5AZyiplcuI0lg5fxRaSJdrk9nGAO8aeBWcznle9kbqKixkJo881cNltvh57JcFziWuHIO3GiIW5sET9DabaHoGv5AnP40XTT0fC1lSP9sVM2yANWMkNc688zYCFfsz/+jU4uWkgSXmasN/mEYM33UPNeA4TVmZLAORlHprLZiKyxEVpTYiC9IXCRayrr7T0yEQkclZMD3jVOvshNWSZGqpHs3qeEV5yRlzCVPBcX2/5WmE8ayDLMdikoL9F86AP/dJ6DOt6Avxkm7EPL9J6KC1mtUwBsuWtcp7mw3XMN2NM1/ZQYS1J49le3+GKVXD+Zu6aeWzdiJihalofm03AHvYfly7CG0WikaJMLWWNqDeQkRMnQ+p1qjj9379DQUf5dTkx0bMXnPITxY7LDXiaO9zflabiYDKvbyOYMBrGLEtwpHUU+tqCGN8dM5qAeLONY8lGIQe2CuQaLWc6X4GB5cTYWuhl8RC8WECINud/U/sSoe1XlxTbu+cKmWY3tOT2kD20fTPP9IrDWiEycc7Du53neXAxL4GBxUCyAJIgnz1i13k77t1p10nEhQEBV+VVpHAY71yio6X7+Ohn+uAn7Gnnf1AI3rqnSU8azyeOurTP70xrxojU+6IdB97qX6IUIm9cFphF8elcTJ6s1QpeqqZlCAFx+H2jls/jzCtD0fl6mf/R2jRbP5Oauc/n8fBnitQ/0wzmjSkd6eetXDMDbLRWwqMHr4F5MX4y/fJtBfZnEOWqhWrogwx4WfYalUpegCCFOZ7MlrbKTORWCzbiTxhlKpIvNyLf6Vy3E2s9cwPtDseRInrhhnbps/lRr8uYlpGTauaQ+EjXDG1ojEOoJMF9LjbQ25HbfBiDnqbtb4iZWgo7e3Dg0mDpRcxlk9tauUFGAk2vCA5OMcnHhh3c18htjT+gFU/XDf9eBQHukWtkrRJR6ZsRFUB7tTHF3YWVzhBslaJcgSSdb1q5rSJT5B6P1U5OqzADgCUwCv20WosyI6qXdV3LbAIOUz682vbKRfOKn3N4JHjTm6T/tJ4NasdP1Epda2GwUI+mn3DwjtzHSN9n6lD2AWnpKoNlv7hp8T9SvUFhprHZotkdgm79T7mzKO8caTvvRsL7p3CvYP242yGCRp3uJqdL2GUbV1nN6WRunvV15Pl5ekKFOMzYt6M2He1YAi33nNWHSWv/9CVFnRqn1ksCoNl1lAoclIWjScxplbgNKTV2mf7PIa628tyHMbP7+KLRRW3FeL7spV+Y7gLzZaI3BaSkfN+L1VTUmTSY37nSlcdbJ1SbpaaxoWb83A9A1fsakjw7i/RoIeHdpC6dTwZhyS7rGiQNmjYOLA4JmAmDaCUkcr0jZ/ApgtGlFKbPTmZCk9SPxYuSNVtTC4Y/73et5IabRExWnfg8fiuTERuWElDXTa/NZGlAfvTCd7mQWapy9KwMi/niVERD+YiwTI56j6/D0jWmSqsPS9FnxX/sWwOWxwI6mLUQSgVpmiUks/sWpRidZPk/dHZYHkc7UcRvdG99NmZvGQvwbtHxB7y+aSd30Ktxr5LDHzCygdsffb8Rb1mbBZpY6GPNmqWQ5DQxeAxAXWPn3t2+1mmTLdB3ZpyKue8DWUrdwOQ8Ltg+vwWU2PFe8LyznZktIJEk8tZIkyLmYr7AhtOSkG1VOwWWCCTX4QgzquPnXwplr69VJra3LBAO/VVahza9585iYXUYaMNKvlCkycCq5LeIt/FGyfAYih/S6gjJRoWviD7V7OIaFgPEJPRzn+IGvyiCB29vrnQI0CnTJf+oXomY7iRojg0pwi5sLh1mhITave21MtE+lmBF+aVNrKsUEj4FUhS7uuCL6UqpRj5w84Uf4FTacNbKTZn2SDE8YiIrukTe9d2+u7QlRtSadS6DsAgWdXAv45Nei9Y6XS6OcvwNbvmhcim3egK3dUfh8u8FpBJqSMDM7rdCHpMUId6Td0XKFLTePxDOgD4JxFEaOqMvSTHvXwtMtFOBCgnDz0RNWwl494tV+0pCPm0tw89kqA8yfzfwJCwRAsw1NV9Vj1l04Q25y6AtEIIU6Mqphr012vzZT3R0ZlwadpqItJEpVNzpGjTBodf3IJgN9RJLkFKwB6qG+bh5qT5xwAdinxos9Je9o2HRdmEtcxAld3HYobH92tQJeo2p0kt3GEZebzH8uj+fIuQy8sB5lWL6fmYXryjNObh2KLefsTWNLLAVB6bmpD2A6ZMbT2h2SKbmMQkam+Gp85n3rF98hIYFi8yocbt2ZU1Ck2X0T26GsZUdHUIJZtoJXondhVOu3bE8fGUTT3TrW6z5pdYWyThGCKs1rCn9GW2rALrziyNdmRnhngDo3/KgTsMKQW5H5/HD3V+b6vbEfLqqwZN+/djeBNvVYEIX8CoMSHmx5JGW3IHP9PbybezT38VVYe4TQCAIOsfg00GTxox/pl1+3GFjMxdf3eKvm9jJQoad8SY9/enuu382n9k+MWcKSoAPZfXOCMn6nLJl9O4/u0iFcIfuPbAcfOmSDwmRnjXlmHi77O1EVvT+J5VCm+AKPUwNV2ZsnQoMOmPKbaXknMQVoO+6IPpYKinHERSrbPH/XS80mbs1gh9FrJj1yXYdCp1b4X7PGBbTCsSXvNk9LS3jExpo5vziq7hOtt3KYdLqepCti/F1yrz64oUFeIbfx+3LhYiApCiEP4/6eoFlzfoT7HXK1xhGLeyhg7nDSZSFXdx6hZBZY8DHOXD10tOoCHQ7qN4SMdavd+u4JrkTpjgdbOM5xzOReSZg/zxYWxPQBDSTB2GQrvK/X0KXt/rT5UF5RMp3SQpc/b/Yh7u9/3SHAslF1x/GgSs3u/nRknTjJ4YuHOehwXJUjkcH6n4kMFxD1gah8hgjdfqYGWAHjkAvtkOpizfjXtjvo2/0+LTU+Tcb/SkYxPhckFJKgdBGCOxxT0d0eSx7mfxM/Lxi86JsjUFTAmLEQCQXsw6MdbVYaAyOq3W/7CPPImeijtK/K61EL79nsr777hZp5BfSJG377Sr0tbsr1ySdk3vOv/C2tA/IWjchHtGGI8LciDgALFw27T5Hi5LCbE3hIDP5tnzyRNdDdwxbp/evbL9/fzrNx5yB2nRSgQN8HBtXVqZI9feC6DOzL5a9Y/oysGRk6+XuEuvFWXd6EbMnXoIWkcD5An3ans/2OH0JXwSNNC7mwYSKLY2AOYZF4rDjUBeHrEuSyxnl4h9EEb+oDU1kYDvNXwqz9lWV/c/GuVrESKyuOfrcMnLKcZHvc0X96/iy4QKLCJ6LNFnJMm0WuAxU/FMhlDfaVtut3fYYixIznWt9FpR9v6190RbnJmLYUZakGEX0Bdw/9k1ejznx0bnmyM+3GeiKlL4mqrwg1xYbdcuo1hFqiEnVCldSLwOBj/aL1YhFAd5eJJnLBk/u2oC7cDxgsyDmfMpVj17B9JNj2waxSsVV3rV2glXnZ18Npevl1x902O/mi6t6UnflzZArft2z5aaQBq0hiD6XrBPVH+lKCxOIycO0Jj8Ww+hX6YqEU3JmLPWNe69vYzFBEefPJiL7Zt7PDz9Fxl7uZrrDV5/ozEjn8mUtK8QcqL2iVeXXoKSTpJQUfg5GbCvB4a7VvawD7OmuUeZgqtJySxwsd+0Nt+GO0q3efftAe7uU8anBv0jJJMJ5Kpt4oEqaxC6TJGYl4SL9H/K8z1arFOokS4Ffw8pNVK0eSLLcf0I6C+/v8wm8Orpq0ujs1YTBYY6aKNURt+BBe0kDBcKIZNDu+9RtUETSJ/XRFdx9FF0qeAyfLztHHZHsBuGIfce3IQ1/jmrU/Z2nZOliwazzEnEvpRpLgjTenWewqcQkxlldJX4Fwg51IzX3BU1sBIamoSmCXWVC8hsx/S2iie93DFjKyxMECT2phnH7vm3nlUvnJXFT8ksalXT31mqfUNLMo9YmErt/OBGsk+z0jlOVTxbmobMEPvszWYsMGWutXR/jFjqfRroz9pzmqqf/BbhdMiAVhUI67ImEcAkZNmae2oA5nWaJkMvp0df4dV0D+bVburV50Q/tCv4pGxL/prDd6zU8lIrg/Z26V1/FwQ/zcNzwoWt3Ups54EuPTpKrFr98zHthxZyAbYcUYOGiJICn6hb9APzXmg55Esd5jaILgIadRChASu0WrKf8K6qQSZN/3BepbUkQhqIwSAGPy7LsF5AMYALfPy9YjmRuHF0GDGJoZZ0rDZNh8d30iGLbYwEnyMjOumvJ3hchTTJEehnTmLrgHY4+NcFbW9DR2tnw/J9U8fGFBlerb2jzYKpIXakboY4FNUV/JnKzW7HHFmlX2x3o+3n4inHbQst8cSyRKHvNAIOBQU8GdeR25d7kW+rmL2Ww6eDpMlGmg3SfE4BdyT4O7N+yy3+wfDIOZ+w2zdgyHPIlGGPCgYoPxA0CQvQxmc1aIBPlNTpgYRAxwiS5KVQo3sB5vPkTHfzjQATw/S6HpexIweSUB0qAjbc3xmRbaswgA93GerwdDHjEQruur7Ux8r+0VlFEoz5H0VshB5q370nlyZIjliE2xgIl6577lLDZssw3Uc4Yj14gtVa6kQy2hcyWea1bidV16bqCrdtRxR7sPH7yARSOMTiFJY0Ve7sJ306KRv8ZhAxhUoi9XBVxe+ql+M4hXee/+jayG2lCVsTzQD2nVZ8+FctEqoaHaX6/nNeDpyrF4AI8kkYl4CdXvShJ1dTVLb67x5JMJ50T18PQbDWXefoLeiPj1Ai/HuuDsJ0ERH/2+1ptIrYtafpVbai33YyG8wZ94GacQ5vwMIezodcasCHBcHmIdhateS6YlmakRaPIM8MOqV7x/Sg1tWHX2ssW+1jZ6efXdQNBrb2QJKuPZ+LDKie7o49QftFx+0Ja/EPcUjjs2dowMFS3UbR50aB8y8AwP4WXOXp2QhevFH8ZES8+uJ46ED5m3JRsBwsXPa4uRgPrHd9pM3rQjVrFbzIUYta7gn8suh1eMRSQM8i/YWQtLbepP9Qa3UCDGwwAfVaTJFVxwdXWLdb9emO1bl0XdnRqhWkUvWDz7QDyfZZiK/OtkP+Yh42yB1UXJTef8IJ7zK+YnStBI2mHSYAD9OKIsA3sQQQ3HimrYSZbg67uHdK3mx6kY89ejVvBwqqN75fgVsbD84AdaHlItAys5v7QQOtiz7lP82K96vDF5xurXfp3rZhN8H7OF7t7cozIzV4FSLhw8O30VWxvzB1CVDxe9fuSTvzbUvZ/LBb+4cDGiMBayFfQhXjJbnYfshU3s8vlUiSp12FB1nbxaH2+dfx9nI9UWahHyCobRIF1jhU9/rxFHNNJO4bFW2kPNVvU9pBVFbhkLhr3Dkcx7keFBJ8Zj/4SGNmGxXNAOR36iyhLx8JxedRFPcGGdejmpcKYNO04W7KYbSKFq5hzqx/TFcHhvdPpwSfO0iZunp22AGmb/5kwwjyweiwIxCXnZWztJKu3xS9ZNdYUT3pY4+Hn9dn8WlXG8fRTENml/6IDYoW8Gh5dkseKY1P69S1zFLGmhss9rDw3vF0X1qn16eaczw/UC86ExAsEsx56XR4TF1y/fON2bcGkQ+nByp5hQrdwPpS/XUyTgpOLgeGY92+hkOuZY9vF89xDC7MGNziDpfcVf/PLvL5+TpAs/DwSDi8V2UmiZERrsNturIPsj1A716sGbW81tiG8xlvU7ELK1sixPstNDk7AtL7j7JfKsvTLfBhfetUyUOR82gG1hRY5JfdGlOVVdAqiuVsifcBgAlmUAV0HS/YGkoMMxpXxyKDifvr3NC9ezjL5J0brfgoi4Pu7JOLq8cUCTrBEHw8KMajQvotqJhmHu8ab3XhW08FZWifxkSC2+aHJ9aPmhbAHkU8JpVDPQznHZB8ncDDcXL/IK88JR2R0yadEW//4OIsdDzzRdvwpmZzkdG6l8VHVkW5ltCwzOPJT1TyfbTgzmZCFCmQhuGK2X2oqTcgXroL6Mvf07289XCsdcq5YUg7hyfmVSm0PONVufMJ5mX+/8ACAXZ/WfHC5V9lt6EMCnv3cnFXOqk96Nge4sDFtp2Bq3jvD/3d6XJimOdAn+z1MwYdPWEZ+iEBKLIK2zzVgkFgECiU1kh2FCGxLa0AJIZWU2h5gL9BHG+gjfTeYk4y4JkIDIzKrvs/41ZZUByN97/vz5W91d0gJZ1Cv1wOSFOtt2kIDmKu3ZaTWfWNpBHltSQz2v5nwZI4c8hvd7ttYplURsC+qoPoGjgtDqopPFpIH7eH+PSkwkKdWJIVb09T7q4fQYM4nIn66j+imab/GhDiJ1rx8I9b6FH7EOZbUpcui2KEqqGP7RkLtHlQqk3v7Uk+siU2vZ22EVd1eBOBydTDnqKNNx0xaMZRcf0zNNH9KEPIucg7ee8fNl59wLhkftfFZLQhRJDLLg20GFaNd3Y7kxJHycsoZLhhInOtk9CFaVls6W3+xutf5EmPWm2K6OrFHFQHXUB+6bcCP5JGM9CvgG0142WJoa2bO1xB0HDYwZqzoicSxKnonpXlbUjistu2EU8e5+vzudDK4puTreEva8rcv+uuSOJ9gCeA+M3bdHU4tAa0q3bDX6Z1AeuYpro0xH5ZXhIVpJJ4JooAPyzIUN0Tqd0LrQa56sMj2v4wNcrnioOaks69MxEoG8ELFUoj+QBM8K6z7exJd0RWeOurFA9kCn8bFq7nfrUqWywlsg1xiRxnY4ooA/LvO9ZmN61LqH+lGlu0x5rq2RE9c46KpbmogTxNyvq6zda/WW2GRrHtqLLdn2xLZla/0WJRLojqjrTZb1j4uZdsBazrpCrElxYk/6/aVYOmp7jRnWRd4bd9aVnmn6lq0gXRHVtwO+KpxdtHPST+K+/w0+xYNckOMZl30OxMFfArdWiTQOPTRm/HjPljAOYzv12sGVVse1PfBDnOgxTLhaVUuLSmN4qrQGHEmv+6bW9ulyyHT7jMfKvIX6hG40y/h64hmntrI3wsAyMAokWC223Y/2yn63l6dllBDYWnmmLz1+23eresjR24OiE5Eue2jNnTR3K1ruOKo82zpoSfV7onRmQLyboUfFIzyfKMk4gm+tWndXUjrNGo+iUQNtaK2SaE2QuuhJ5NFGRkPJ2tVHM7vG6Ce+JyMMzlQGtR5/nHmV2glFO24DVG1KxR5ZptVySgheKlEzbC971Za16gejwdztLhdoF51HTGvqURo2N4HLxJBT7XAeGJWwNcWi0lyoUy0/6plT2gbmvW5G9QVJylwTcDU2mZps2QjTKImg5hkRujocz9stfF837JMkYJTsiZ3Dkt51+XrEiHh1sKv2TFoQOhXMCUF2Pw9Nq7ue1Bmn3/IbYccayTt+P7AsFG1ND/sZJR5dbtii3DrDL3zZ4Qd7esE3qHKnP+1EUV/sW+stR/CDluxoe38w9cLlocW1VQM5mAO+RpbHDGljp0XDMpH+bOyt7RlHUsMGgjbQLTM7VkLmOK9ak7N40sV1f34Mp2VepZaK1DxwJsnstmXTwSUrGo35kxhJk6i7Lh3OCmsBoXVGQz5asyKK4Et10lnOFtuDBNJiLWDEbYvrMQO0YlfrdRQ1R06T4SftqXkC5Y9gmZ3SghOcNt5ClqXuuRXW7E5rMSbBuInmfFRbwlv+W4wd8P0qT4AoN69H3RU90TkaZ5AxO2Boh+uS08OgSpvt+RwUIUZ7P3bDmToyltSC7agLy+oZkcYuRGRL7Kvhvt7Du9y83dmJC66uhq7bCSRbK08lZOXrjL8e0Ih7xk+yoYiKz7tDBOPmUnkvqFKtE/QO1SG7LPs91qjVR/X6ftrdoePufq13hJ1cWWP6vsTPF5TqHfRefdWsu1bvMEEtpL0y1CrTb4+OEc7tOawfTaQeYSrDobjmaxXWcBYULVd8Cl/3PZKk2jhR36s1gtQRCqRVuqYMTh43Iis1bHY6B9yiuvZ1Z9226ppMrRrtirmTA1WJeo7Wl5qDFiggBrg+ppaOM69VsT4tDeuaxJ7qoVgquej6NKnPahOy1TQGSKMzoYdqpIAaDiS/vHCa6MtZe02fIoZcUEibwjstqVKtW0aL9YTJArMmexNp1OeSzpQ60ya3XHNOk1hNiXUUoIi6HUd7ajSNBJ4/aZiFDgj9zBOi7hBMReodUYuwq/gwJMYsCNlkWzvR58NSl8tNfcroDL5u9CiUCNqzTojO5w3eI2bdaq/aWuzW+HHC1sYqWu4eT9h8SDrbcNdw6V5nUB2dZEmxdngrGhjGUuj3uudgtuhzcqTRCy4qt9z5weo2mPkgmsx4pGrrOjoQJ5q9VlRy7CMnqd5etbhx59yaNr0xmDBBpncRcpZR0ncH1pkWmoOmvMbKBs5Eam0c2mjXG9UICalPy5SyWFoYEfVW/W3DGnRFnxz1/YVD80NHHy3K3d0B69JMpV9hkYFBz6Y+1eiz03F3OD4rGr5AJyJVo/qlVd1sN/uUvrXrLXS+H2nUdtKrk1O/7zdt3e21bd/p79qrWVPAK16EW+UZZe3KA5WMmnvaQfhhF6/wTezQrLploz4nRHN6ONYOa1qll6fzChQnKr3X9OUU36Nmfevow26viw/GUVCTNW+4KLcGJcPgJ9PA2o9J+XzCuxYnDwYkiyK6f+juxL3mmlsBpLDtbbXV88eWMRxhjZNq0W2J9vBZQz5Ims5aQXiQD74w3ennNW2i5N6y8dVSdZnW/DDfNpnGwew7i6EyankzzPCm56YwF9hAJbgQblTvJ4PlTOOqziJaLdShXQ+tpV9DrO0JtVvyCdlHLZ5SMZdxSoRVsTrlqDaK6seui3sSgVnj2pl1d7JF1Ex8Lx2F1RA9+h2n0QkjkTpZVZuRgjLmEnXxeFDcs0RSK65ynJ3wrd2Y7OSaCDJxSmw1ZgairI/eoB1J5TayWtH1yRgVhq2gPPaOS1TqyWiwOpdBYYeP60ezjDSYztQPQrnHEroyEcwqMdmjVrXsEQMr0LBGjyjXEaYnj8KDaFUr4mpHICOUakyiIy+U+NLJVA8cpfq6W5kyUmdijPTtajHGrBFx0LdtTi75JcymEdGnTj3glNTSacXSHLbTDhrRRLV5Azf6wF+17aZDhXOyzveOrNgcDCWhHOKDNnvGRz1b8qf10W7UHK+1vjHe+R1b7smhN8ftdk882Ui/taO6VG9UH8+2k3FJDNFKZ1G25rtjiygbQm0xrgw6i+0gPJd2hLwNMFPeya7coJTTtFmPpnh7PaXkHVddtEcyVV1PVs0TOShPQKa0Rg2OBo52OWl6lQrJkl4Tmwq1NSX6Jb7MomJZP531Rl0mDpFMdDVF7ZqH6WImEKJQw3hygGkGSHdXB244XM7Wrf6+7K7atbVtkipPyKY0Vfe0ys+1oUBIu57Q5Jrgh+WNMZ5Qd6OInfZczBzvxsuZ0ijX5Naytmoojb5KTfbkdHCiDMnZq+LBr4fzfatCreaNw3jRc6yubK44Uet26aGzwAb90/zktkWtjfPISOdXymmsbf2RbyyVDjEvRRVl3uZW02qVK3t4nTgeO2PClUZ8YyyexuyYrxrTSa/mLbu1Mb9HK8zYa46m8gEHmo0u0cWA3fUUmcH80U7mtQ7HkIGmdEdVu9yY4FzHIs6OUEbYcbTYS6hRbvJeBcEccwzqzLId4GVue1yVMBDVO4rCn9Zr7Nwen8a97Xk1Dqygxzvl8Lh0hmRAT7dRqV32QODudXS0a4vjib9aH2lWdIhO2eoQVXJ00HpurUzRU7zRBkGQrwcYv+JmtdWhHIgHsrqkDFZr2F3H2Juczu4GNancH63HUae801ddC3f02SDaVuSJXzo3zNKiQ6LiMZqUQr2vVHrNwJpVFaOJjfbGSjiUjDLRr+nUOaz4B6+2pteyKq1W2lxcjEtnarTqh2dqzyKTqL8Mu9Udiw1Cti1y61rUitjdyFTm61J3gBGzHreKgBh8f7CbLnedbtXryZ26HoZ0ayQOKtxA6tj00JVb3hZjqJJ7EhaIqGDVgTXyJvtJtGxG2nCwxKLeeObILXfBgPpp2LeotX1YLSlqpBiLuV0idiQ9bI1dQxBbCilQwwUlnst8pcwtaLKz7MojTgzn5lCfsT15xY+0blM76V1Stw+LkodTQ4EbO4PagBxEq55LifPetOHuj/xyWt4PtDamInVKaruO4ZZBam0MDgt7jfR7vaZgnrDzsISTc9EcMb5Rl9qtU3OIESw+WQ25M1PG8f1Exdhdk0bt0XRLaupwoNHimZ54crD3Xas7JYmzsRiPZWNGLhFKLY127XDRGvR0D2T9g1K75nvzLtvVldOoW/VJ2rTLnSrmWjpaKhHoEJkcSfJoDlqCI1e7tfKUNvtHqokIxpHezYTuYWXOqq39cn1c8wqzHI6EtqP7LEZbUbDyJ/ZWnksLam5afBTZtf55O63ymmks2eput9MHI1EfLRGHtTyZrZ2VujdCBGSo7M+04S3FvdT2BNzrj9EWbe45ByVrCN1sH3Ynv+x0j3JjtGxMQFbnVQ3WGM4MfccJM7VmLIanUBTr5KSthErdFE8lrmlVSsAUT0u2bvJTUhi0QCFZ2npc0x1PDX9WokDAmxn0Njif3VKbtg+9UFuNR2iwbW9beHtPu5MeKXf4wDpGZaGy1ZydXqnOpt4C4xaTCNXx2rkhEnKv3sbYsLdgutLWkbYhL0934XA/x+cd29KDecNQuWGV5Oed0N63PJcmK6OeyvjjQMLn27Oqlf15NJ93G8qany3lkBSr/W7dBlEcJ3bH/fjQ1yLMWzZdrzadWkzQbPOHhdmULEFp+tKwdV5vl5zdKi/rkuHTcwnhutZCm9uGUd91e6TnLbylalnT83KxtM9jvSwrvNM4r/AmE3kKfxD9Q3vfDhZsE9hebW4jTq1S76gnmjqRvNY/qo3Sjo1ISzye+wYZ4K1hJWIXtLtnnFYUiPiZmSx4scvzXZWytZanT1vbUKrv/PJWGpBre02Md6HdHDjEQSsvGJ72Zd+ySvsGpy22wrzmjgJsYpCRJuIdjpwF6kkwSKe+P9GlFdvsuxWf2xOGSq+ksDatkIhccemqMuGHRKmsN3teuenUeUSYhB3Hbs2F6mSwPcgNv1+enyunrctEY45Bm26TbhtKNQwPvhaeo/Jx3+KIfktxKGvdaKynEiYJZGu+P/DReK8Sy/pBrtn2OSotLMffrvCKMgTee+BK86puMLYdrGiE7pa6Sn9h17AFTuvIQULNQ2293wlnuuMSsjjhqm5l4E2G9cG07s+wxWi9m3a7UW07L7nAqKMRinW5IJD0mu8POdVpV2qNWkhZUbc+1JnyuqLRXbpmrym1opzHu3atv2wYx+As1to9am2h9kAGpoQJK9GJ5lZ1sj6rI6Vr8yTVn6vSYD4L3e26M5Wrxqk2iXrrQJ+7s3Mv8KKOTljMbic5Zbe13h9sZ0KRwANKVmU2EcTJlGvM2IUsD5RhhWf2bUQ5l2pHmWOHFEhzlmNuaQbVWVPazZp10jZUt9qqNyy0ohIHER/C7aOhW1p41Nh1msKucRYqwyaqzzvn0qI0CnF7WtGB66TIyvqkHFilLuoWrUuRtFjo27XcdTmM2oXAA/ZM2Wz2hyLibofRAegFJjPBUCVKvcFQbJwdSusMeo3uutsVcG7XbMyH9ck0lEEW3a1rba67b48kVSJ2M0tEd4LXdPnKehlxVbbZKvsaFkwD1WpVa/KZGgANDko+sXMi3gQ12YwYUgczcueLbaQt1UUvPIAs+jBnWxFTQcNF2zgyB884aBrFIlR9X5s1hqV9hNQq+L7Bq9NgTh84r48gfBcjzeVxoAXlpef3Wwul4QorX233zYGGVE/+ASXcnh+xBMGvRvUlI9PkqtOrM4dwApJM/3BY9kdNA40oRLC1UNpHRrO6HDH9sNQ9uufuSJ6726W+wOQqLYvT7gGjTcft9Ob4tD/y6LUeym1Xwbshqo8suoyV2DNHlAhqiR2PB1bUjFO1NaER3uppNckriYSkbMsisWp0tJ3osIeys18h9grp1nTVriGOPZsz2tJFGgIyZeqs1Sgth+MT3u+szMagKuARR5UtxnPskYu0HGZLctt6aakSjShkBWllkKvm1tbQre8tpUqr12merMG8Km+3y3Nn2XaOp747MBSytmj02o5rNk5dSppiOk6K4bJl4jNFLK8Yv7li5ApLDs+NlXvSQUgwp6Q86ZUbe43Bq3u+NF5X0e4QmR7axMDXhf1Rm4kh3gtbson79S26QijgeLuL+ZJuAJczP4xVG9QuDdHFsWDV8iRliUSWpXmMq2wtsRwh4gl4R7p+ZBmE6ezV8qHuOav5rsfX5i6xZu1RjcPtI/DDbLc9pNFes+WzTTZajfwa5VrLg2yfQFWG1odeNdrLTE2ZbDtao8Qf1vosqo3b05WEsyBv4NlRAxUOVPWMmNxcb1MEd2QotVcec6EeydKMNrCtqZ5ru6O0nXtDvrqk68uxMZ0PVbJHSttAG81WDXNS48fm1tU7QrXbICbMhKDZLX/kh3gFITh1PmD4ur7nQJZkGAN2WW4xHrIifUE/+AQtcM7WqM1cg1+fmwef252Rc/0sG+hhPZxi5YEACv+Vwre02QmkyOJi3vS3esOQ9yEIxyS/1aLBslqd9lBWC0v0eorTam+Pl9itgIYDWrXajfG4TOKLqjqtnReV8qwrnetce9KzRIKLbKvb3Vk22WWwDjWV1yFfa3dFZCz2t26nPsaCeW04ry4qUldpn6toexme2mdmIJ+WrcUpWFewAzZDxkG1DLStLZFzoV9y5ianki2rIXJyhGGjo1AT8XVUb9SrwOu0/YkyH3nKebE2tOHZQ/mqjq6rhhsug3BBmPI46NkIMnKwsjLFFVSi4enNxmHiYPYwsEZBpUXXZuHJPyq7CY11ls3qwduq4YHqnpUtKB54mwPZB0kGSJdhm7u1pM8b0REdECtaxI7BcO0eTSysaNLa6AXT6KTR5qK1cpbK0ebp9mTcHy21tUQb/fVpKwzxkz0dS0tKPQh9ao5xs+OAGHAOiS8PJ9pYuWE07B1GRKd3PixmpmBiFuERvhwKc/KADkBu3F2pwwnRm0zwRaXd0PxyWAnwQLENsSti7rAkLerClG4T5ZU79zv4WChpQY3EcXyMtxuY3ULGAnnEIlorR1NEExaz7Rw46/EW7Y0HdYHCwHT1iIBHJl32pDOILKGs7Z5DcmqcYdDGQCxxRgw2WTc4t1W3CL59RkVn1YuULssxU7c3QxbI1F3OF/FTrCVZKcjmVpYkWdp4duCK8uvWsLdfC57vvhV++3f4mT6mWfYD14qfO12UZNEGvlD2vNfkYdbFba0CL0oJ+ttbMf31Ej8E/eXty5fkseAb+NxljpmzbbLw7aHr9KHMb8nC/KbNDIdke8awn2PcVvDvuug18WoNIKTP1C56OwFcSJ4t/cBKUbby3L4Vd/JZ0lTZ818B4Qd2fkT9Oe8/64JlmBkgCJ/H/fpSBO2QO2YOr8VNaOEleSh74DuBvzlixEsMwvW74+aQA2AXBAApBq4rW/7G01RLMLyi6B3BZFMMu2yynWdUleSB7AnZCxw3a86gzLN4AAE+BF4uwoeT30CHZKdLso+whiypspv0f2lKpuwR1pW3ggGf0r2Rj4B5L+7CeLlI/wnXMdxGs3zZMIAgAerLF7a5vPVwwwQoCdWNK5wulK/NbWZEPoeH8ga6LqcyTAC4+WjUZPnnCIYsuJZmqRsvME3BDVPhj5rcjGSfjcIUPF92XwDEuE+RHGzPAEMowdIUoCapzDsgb+M3LDlh2EdYSdCMcJM81j7tuT/uz/rN4abdnPRn8HM4AWhYaVMqxf+KpS/MmNwsmzxQ2rh7cKmEVb80OVA1QLF8f5lOpy/vhRey3YMf7QnJvnx8oVZw1wyQ+7ZKXYllnzZAXq9PPcflufRFAPV6eTR9EYC/FTXPBhpoCn583XNk8duLBxyIJXnQdUDShi0Kxsa3JSF8ffucLnA84OdriuQG1ubiMV4TjxF7tveCaUuBIW8swUyupCRVMKLfb8+S38QAm83L1yzCexYgfkMCBFBe/u3S1dffM9B//PtLDgFkEYavWV6MlP2ZQP0R/5XPsvgKfSygnjL+XlC/3/r7ANMAgV7ewHXw/1vy4H0FaotmvcDXIhQ0q6B+vXadPGafDSwoq/jx+6/KC2kUzL//F+DVjj3rVpPsQo55QCh+DYMmW3IBkgYSfkk6A+zEfX1cpG0AyXsXp7NJ5uHrhS/IUMZfFeWz5vneBSAznWOgFfG16+sE4H+SAmbGkYquLEgboNevGVpvVyg4ftjvdfwAzXbB36JsOn6G3LP+MtdAR769uSjWq6R8T8h+vBVN4XxTsmSq4tcakPGHZlvPBxQLCHjXjSXLEnBCsgKi5+4VaL0of6OAj5Zjm9natnEVWdz4QG7mBgm/EpDIM5HnbKPwP77lTSfh5ORqvry5OJbLLNxcSdHcS5r7Gk/Sxt5/g50mhC84eUMRwbz4ICrb7kbcyeIefBV86AqAjl+dQsYMvPhtD6Dx5clrUbL2orh2JFswLm2SGAtwHsJ8Bj7xwaJtwJeJAG6uSM9D+GNPjm1oYggQXnPK8jIUCoJ7CIDYRCDZ5FUnF5sRYisRzK0mFCTQCAJSIY2oBQe+4qRYeLmjZnsFK5CP8BUlII+yJC0SdNkrSPLthSYAzwdWJ8pWQTAK7Z0AxmTBaHqj9Zb1GZf4UUwmF7455TYGGDqKUmA63utlBt+BgUhAWt/w94JsefA1JoInalqqjjfRxJkLiGjf0tzl/fIOjYzRO64myl7i+OG7Q77HXlYxbMH/uLzm4wR0JlSKkn2ywHXpxlwaaJDCd2r1cesXCECzpW8vWEnKqIQQANMUJD3w/FgtM/CurcKcNBnA7bq/g17Du4NWXTtwNtvw2wvQlsC0bsOCHyDsQw1PJAvmshC7kxyjX7NuR/Pid42AFOQVJhgJSe8depJRABx8H4j6/JZ3QEYJdJGBLqoyTB+OsrE5CkYAxFl6yyNgP0PA8giAsZhvo5Tv+eI+AK3v/keuSTauSNinSMWz9wr0RwDu4Rv2XohZ+HbXtwzm4JHA0yg0toEVCC5Q9cLv/h9A34AdeKLgqsIl1jwnmHLz5XpRNGxA/Vvqv63ABBokvkrfX9qwAQZNGXbpwTmXgXN9AZ7ctR1LeM3FkJjM05DxjHsOyArYsKjZ8C1GIFAC6wejEeBYsvwDlQLCBtzFVvGadKIB5/z9N+wjVbvUbQPQS9YDw10+m0+MDAyxI/gC5cIM5k8E2ccRQPHHgHLhSd0AR/Dl1yKwKwP/6MpwVn5P4iVIUgTPk334xQfzCdQVJqagHNbszUnW1J3/kpiYqXkefP3QtxuV3woAE8Tei7ZfU5wU9iepTfzmIKuQIAuxa/Xkv/8fwfgKMpyEwh+3sV0C/FV5ngX/XGRVvsOWZHgfRWj/r4l7ePsAHDvXUJvGZk0ClL7mpi2fJUega0Dx+69L7uPaUYyfGcL1exHUFqEDUkiQ4SZJ1Rn6tajoAWIXp5H29AaHDScWhoVzGgWyQ74rdgGp+6L2rqaFw9+Ckm5/rS/j2jFRYAlEiVwe/ySd+GEOIQJ2NqLhgOYnJU422dgB3+IBsN+Fr7C2if25cPPnf2RgDeGWTmkSwIHZ2yftsYgfIMTADEBQ1I4ySEMAcMIh6DYDo1marwEKouBoPvz8hVH8iUzoj4zz+KHkU5eRK/g/z8yfTmUMFH8HehVnGbBb7zVPM3YacUZyn0y8ZSh8fzJIqM4Pw8yqTYyZmpoAhJ7nL/77NR5yOqA8Yz/JlWL0f06idF1igUaX5QskCXHy9PUhcYpnK/6asK6coXuKgWECkkyhdQTWFjtdLzBvg0iCTCrW1AI+YMLwKrxDbXx7K/ztQkv4AN+V8w03bx/pKDIyzxG/2iHgF7nykwxacByQ3G7i9ZZX+Oq5r/EK13vB3uq5WTlp/i5+N13RBhjAJb28P4jzDb5ITrmppZLM3mtmvgDZZ3P0Dry/IoA87Fu8rInAN8tdFhZSFoHjA7X1WZZybLr2KcdmYhtwFiCrF0v5dASWfDI0S/728jia34ATeRgRzJBhzIWKsIRjA4EMKIMmGxKsxr1vBujwFTBV3Msh6Pgtl7ZAU05Yymctp0ROO2CDgOANJb0OyEGSlyWT6ypcqrAXG0hzgou2pgLZygAMmv4T9b6CPlXeJBzFoc3LFZNuMY5HXwuw1IZ+M1U3t/hJIMxIAWquCzX3ksHA8fmBY8iXafrjvl8QE9JfWet4iBFfLg4TWtkFIQ2gwJb+vYCBwIIUMPm3xo+zrYnsgaoPKCpIL442IAffMGkVsFLpX665VpqH5cQC+Pxn23Q6KJC8Gpq5ATn3JXsDfaUT+7eLcCDBB5nEorTjCGbHSwI5FyRsvdc8bUjkt8vowA/Ib3bt8SceKP4QFDCll/6uKpKy+1uGnWS+86PKIP94ZNmgdJH0/XRkBoUWXvNyf/uJ4DPkb/7zWhtk2Pwtlmna1U3hclHzWcoBiT2NBrG+PEW56BCSEWJW8o952s0SE/mniUzy4/0Z3G1kKeztQjaHurXfWMm0pzP3cjXdXN4DV30v7ihefrlPezIbD88XulKzgBN6W2S7LHEkkk/8C2x9WqKlQHFYvhYAaWuWQpxEXoG8a96eXWbMLI+/fcnlW88yvHSqUi8OGYhD4M1/3ZTgLtl9g4uFgOds4gfIxDXZLwaFK2aqmXc9fMQjlX4Eda1hMr/z/FyGFS+E3uwxm2nkwl9+3+k91/b7wwLFC3wTsSv9pPi41Ra5UiDz63PYuKwAUngC8SdXO2/2FUsfACdfHiH+9rdYdPmGTN2T6lXsXv5KMI9nAEbttKb8b4pcIG3Jr0P/0uTdT9pzg4hbn2Al0/e5Ef0Di9eHw2ETeNJ1HpN9t4/s8ra4u4OAW3JZCBH4uzuQZLsuAwOaE+d6m8E7LuJZvHjozLw+5+hz6KfcfQ7+wGmmxv+s5ngaZrJdxN9/WqDnyT8LqNmeklAIph36RIDk+g87BoktoXnCzwp/WOYVsPs1/bSbi7/b+DvN24DIBvq5XX3PGsNDIZPfnI+LmTT0fFIn52o8AH2pCECQcYVTui2fBFP4ZvDvMKJ+5FYSbrvvny8jfP/ILrF//7hVTxnspIZyf6UKBO4BFlnQQyh3C+zw8rf4owgKP815fVgeh0zD9seV6njX0wrkXENuTzKzsFtMhP+aWQCBVN/ulsQ/3Sq8bmEAe3i6EGwK7h4YClAC33ZDOHmb/HGDV/BpaDBPAd7u63VTPBV/rKIwI8xCpekF0D5HKs4AsCQbvvAqCaH3rfr2JO3481s4cb/f4r//3Ts4nuxqSSD6/5s4/+RNnAfT+G/amkm3TOAsPK7TZxrfin60iXe9tUh+heuzmcQ0VotkIyZGuSbG1OpyaiCB+emmyU4IC3Oug8IDNfGGD2DkEMhA2QuxbdretaDPbydC7lM+rishd1lOTi+Fzxh7OhmalKEvfCQiuRmfAVIVEE9iJpRz0ZXj9leA9VZUFM0wgOcyNR94gNzOlfCRJQoytBuh51tXiXsC/4C7ih0NAADYx2ty9g68qQA9+0bL2JXkJ1ML/RGwRdN5wLvuA0k+mGfNUmxguPEqfOa4CKQSt9/04GU+a6fbcXl9zQADYR5l17/AxiBW+NjcjNVXQMfyacPb7j6lm5y0SEu63CCsMPW2b1d9A5dixX0r/Fsh/oLVQC4MwpslZQmBac/J6ca3CCA1CAO9XA7me+5X4d+/ZQh+PJHAr1PKEbqMxACx+kbirfDtW6H0+bme9PcN4XvpI12/l2MLA2qzDUQQ7l4vSpELu8frMsn5F0/gvFhyAMZhvFwYPoKBlIr4I5MghfQ0mPdlQP+t8NtzWEtWhRvsQ1/xkAIHDnGTP0t4vx6RJFZxnX2Xan3JJlfJxQc+8jXs5ZhjvG4CN57yNd9LysMGpHfek2YQ7QMXmBom/aCx+qNGvHTXelllFFwP5rHQJG55H3R7sY7fD+4h08riX9Ktx/wpa3Mg3773HfAEFwgaTngNG/l4lzlt8MNcLc7TsnOT5e5xhu4nBRpMcunt/XFKUoGluV68yvmz5M/UrNcsC2niCSkmsv6xsC8KllS0D0J7+yTi5Et0WMk9C2CXIBa3p4EsHcoPUou8uGGwSnG+x4Q+HrODZAfOjyX2EHweOnqqHCDVO9/Fy7xWpGNJunmIOj8eBPCcMCqkHSRpny2+xrSejGITDzpxdBAJHhQB/y4nRa4qdrcEcncSLl6tSOf1euXZQtaDML5+rg7PVqCCraF5uyfoDy3P0JNlAF9Qb3i3S88QZJgrJ2cE4sML6UrCE0hJc2XR3wD3JO4AmGb5j8oQC/2hW6iovydkCy/dIdNqDtPTKjnleNInyALd8DaU5OfT5cP4aO8NMv39DNTXfCMDmfx8BmiAyhvG6Gs0vSE9NiWrb884u4vFcNHrPjz/SI6fdfVL8tNMRwBztpfDk+1KwPHFa/0p5WeNMHF6piWxIXmgogQeHFKAv5+sqn+KGi+QpStEF6u8W0TNmyP0hDuoON9BSVV9L+Clj0f/oMXH2UEFugPJBYwFzn1VeYtCmv+JI4DoH29PsYBP+K5Au938vvsj2bi6EEJvziW76PSIfQnnVwqPwM+Lw08YsJyiJVh/psPSg6O7xv1kuzp7Ku16qAq2pYvUknI50XQllL/j4zaTmSNPnx7niHfs80sM8R0eWjafSSPp44nzZLEC1Pwx8JdPvN/7lx96ubvmnGu7a3uw31v7Rz5ww6ME7wU1OS5fjPnchq83ft8LSahNj7vcH6KHC+6wQALZ7GukOTlESPpuDSxB+P5ipTluPNXQBtS3v2BJqdIAEup39YkSAbX9eDyDmrCgAB6uygY5SJHv+MjUOBeAT5Q+ztRiiJzyP89UHpgxZcHa5EzmuX+9bee6RYgDTx+k/LlvsU3+yNZ+yoSk/RU2INY/lZFLHQaqIVA+/TIvry6s7N7+KYL5gXv7fM5+5OZ+JORfwftEJilqDvfqma4eMyZy2dnO+ssr6Nsn3jK92+0fdZaPpwd+UBR9+axehUCSkgXIVax5/YC5HjykewWB1giPU9w0A9BKVKP0dAMmV/H+mHj1LxNPKuYfU8dLf4b8H7mjbVJoCaYmpncFxsHz1+73uUS07B2HT/Z1bEO6OxqeRbgZliWfEjhQH4nCXfr4HVB5z2vmd8Dpx9tHPrBpqgUPmiQ6mN8PiBUfjPBeNZ+t+V15ue8uXfOTTw/WkB3UP2IM8UqXD+bV29iWcb2bEaSaYM5f/sN6ckdU4f/+r/9dILlZs8OkK40pdHwXUnKsHWQhX0EenD3+78qebRxBrvv+9K6AHCUqvV8p/g8Syu8eZmndtTwlRyYL4PGWUUwus7eXIfVkvzBHhklXzK5c5RO4LKm7lqfk2NgC5Nsgc5qdIfZU4x8ln94HnsjrfmP/7bJzB2+a/HpbA4N5guCq8fdi01UDmKVN4pY0R0jAioIE8r60/aaGL7/9pgSGkb0jSoQLVN9e4PKIvPGBTWQad7LhfHuhQAUaCTCU/P0/DRHe7glvLjVk34b3RcCx/JbwX7zq6a8wkqjxn2OF+/t/ge7NQPZ8uGUCSEh2vlfQVXLENu48/oDdZ5dD4c9i0vvX3Gmiq1HdrcElmPe3PX7JW94LPBn87aXwt0K9npvsZzcp5gCeIVHx6Y9CRlE+U5OETS8w7k7C/uJxlj93Z8DD4qr27MbUWMBQz+6S3ausvmNo5aPQFP0A7q4IlmTn1KiYvfMpHl/2VuyHPOfhiQxPKvLkQQW3sV6o3VU+9+VGLNbvLxAjHZycHES73kj7PNm7G2lmcIUw1tu//ydU92T4klDY2WGxwMmgx8DX4LUHCXzOSuaE3k/v7M2Ruj80J2VXNeI9siRDSO5BfrauDU9TZEZ+HTXJsgxbSPU3HTjU38xWKrBfUd4K4r4YY20A6Wc8xnMFN02TY30+SDPenqjhTd74g2ZdgtMkvpk2p1vKKd5qfjzyec9IMdmKeb3bLnl+ZghQ/f606S4bebl0mniZC+aT40H3iJ+cQoLYT08f3aHfzgDd+nw8K5TB+uPtr01/TvR/TQEuMvpTSlCGSsAC/wdv5I6V4HpjNFIwZVcEYQN+E0TXzmvE9ZaETHIBQ8PrWzE2qEiGhvEk87gk019+7rOeP+Plfkfs+owS75mzyqwzxIeg/wGOH0SeLPXDncRtCPzIRoj7/ricmH9Pe/wtFdbbX/QNcZZXaF/utv9r6nGR0J/RjgrUDjI9bgGVIz1wAbdeUspAP7yCEgBDBJ+S5jm2pW1BlpxXFhnuJn+ySfuLHuSujJWPmd2Wy+W39yc4m7va9oKZu/wcM1f0XvAyF3+MVX2GVf0ZVlKm3qPBq2//uJtJNGmY7mf+A4p0e/7Oc4X6pCZOaPxyQsiS3HwEMoFOv8n2mU9ywesjWZ4FEriymfZ6L5f8JLRB9JBBpnxxxF/v8h3l5X/+fhHBvz7p6V8/vr4XS8ofhfZw8vLlMUt61icLCgPXsn/Q563LfAQEvSHF8r/88as9tUGAgw/BADGvmBZln4/uSWD8bHTZCeHi+jhJxC+F38Wkk1237Invp2VsbMVPMHNG/l54GaOdewqpk/IKmFf4jELWnn9CpfoLVKo/pYKXvJ9SgZZ9I5M3jBnTYQog9MB67ygUhJ0NNBT63sAqgCLaBgWauNOO9te8aYAvYSF5jJklx08yOmKbetEJ82D/YQGldwCjheTZWJDRzFrVtU7PIcGnGOiyGAAsG95SJwK3I3vwSA10+vAwFzDFywOd4M7Ay2YDa3P4HKb0yTawUP/y/wCUarkQ"""

def embedded_source(blob: str) -> str:
    return zlib.decompress(base64.b64decode(blob)).decode("utf-8")

V18_SOURCE = embedded_source(V18_B64)
V18_SHA256 = hashlib.sha256(V18_SOURCE.encode("utf-8")).hexdigest()

ROOT = Path(".")
MASTER = ROOT / "mfp3_master"
EVENT_DIR = ROOT / "mfp3_event_intelligence"
FORWARD_DIR = ROOT / "mfp3_forward_v17"
V17_DIR = ROOT / "mfp3_output_v17"

RAW_EVENTS = EVENT_DIR / "events_raw.jsonl"
EVENT_OUTCOMES = EVENT_DIR / "event_outcomes.csv"
EVENT_ENRICHED = EVENT_DIR / "events_enriched.csv"
EVENT_IMPACT = EVENT_DIR / "event_impact_by_category.csv"
MARKET_CONTEXT = EVENT_DIR / "market_context.csv"

DAILY_REPORT = MASTER / "daily_report.csv"
HEALTH_FILE = MASTER / "health_report.json"
BACKUP_DIR = MASTER / "backups"
TASK_NAME = "MFP3_ONEFILE_DAILY"

# ---------------------------------------------------------------------
# EVENT TAXONOMY
# ---------------------------------------------------------------------

CATEGORY_RULES = {
    "FED_RATES": [
        "federal reserve", "fed ", "fomc", "interest rate", "rate cut",
        "rate hike", "powell", "treasury yield",
    ],
    "US_INFLATION": [
        "inflation", "cpi", "pce", "consumer prices", "producer prices",
    ],
    "US_LABOR": [
        "jobs", "payroll", "unemployment", "jobless", "labor market",
    ],
    "CHINA_ACTIVITY": [
        "china pmi", "china manufacturing", "china stimulus",
        "china property", "china economy", "chinese demand",
    ],
    "COPPER_SUPPLY": [
        "copper mine", "mine disruption", "copper strike", "copper supply",
        "smelter", "lme copper", "copper inventory", "copper inventories",
    ],
    "COPPER_DEMAND": [
        "copper demand", "copper price", "copper prices", "electrification",
        "power grid", "electric vehicle", "data center",
    ],
    "CHILE_MACRO": [
        "chile economy", "chile central bank", "banco central de chile",
        "chile inflation", "chile peso", "imacec", "chile rate",
    ],
    "CHILE_MINING": [
        "chile copper", "chile lithium", "chile mining", "codelco",
        "escondida", "collahuasi",
    ],
    "AI_SEMIS": [
        "artificial intelligence", "semiconductor", "chip", "chips",
        "nvidia", "ai stocks", "data center",
    ],
    "GEOPOLITICS": [
        "war", "sanction", "sanctions", "tariff", "tariffs",
        "attack", "conflict", "ceasefire", "geopolitical",
    ],
    "EARNINGS": [
        "earnings", "revenue", "profit", "guidance", "quarterly results",
    ],
}

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def tokenize(s: str) -> set:
    return set(re.findall(r"[a-zA-Z]{3,}", (s or "").lower()))

def event_category(title: str, query: str, tag: str) -> str:
    text = f"{title} {query}".lower()
    scores = {}
    for cat, terms in CATEGORY_RULES.items():
        scores[cat] = sum(term in text for term in terms)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    if tag == "QQQ":
        return "QQQ_GENERAL"
    if tag == "ECH":
        return "CHILE_GENERAL"
    if tag == "CPER":
        return "COPPER_GENERAL"
    return "GLOBAL_OTHER"

def source_key(source: str) -> str:
    s = (source or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s[:120]

def parse_utc(x):
    try:
        ts = pd.Timestamp(x)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")
        return ts
    except Exception:
        return pd.NaT

def load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out

# ---------------------------------------------------------------------
# ENRICH EVENTS
# ---------------------------------------------------------------------

def enrich_events() -> pd.DataFrame:
    events = load_jsonl(RAW_EVENTS)
    if not events:
        df = pd.DataFrame()
        df.to_csv(EVENT_ENRICHED, index=False)
        return df

    rows = []
    recent_tokens: List[Tuple[pd.Timestamp, set]] = []

    # Orden reproducible por momento observado.
    events = sorted(
        events,
        key=lambda e: str(e.get("retrieved_at_utc", "")),
    )

    for e in events:
        retrieved = parse_utc(e.get("retrieved_at_utc"))
        title = e.get("title", "")
        toks = tokenize(title)

        # Novedad respecto de los últimos ~200 titulares observados.
        recent_tokens = recent_tokens[-200:]
        max_sim = 0.0
        for _, prev in recent_tokens:
            if not toks or not prev:
                continue
            inter = len(toks & prev)
            union = len(toks | prev)
            sim = inter / union if union else 0.0
            max_sim = max(max_sim, sim)

        novelty = 1.0 - max_sim
        if pd.notna(retrieved):
            recent_tokens.append((retrieved, toks))

        age_hours = np.nan
        if pd.notna(retrieved):
            age_hours = max(
                0.0,
                (pd.Timestamp.now(tz="UTC") - retrieved).total_seconds() / 3600.0
            )

        # Decaimiento sólo como feature, no como verdad causal.
        decay_24h = (
            math.exp(-age_hours / 24.0)
            if np.isfinite(age_hours) else np.nan
        )

        sentiment = float(e.get("lexical_sentiment", 0.0) or 0.0)
        impact_hits = int(e.get("impact_keyword_hits", 0) or 0)

        row = {
            **e,
            "category": event_category(
                title,
                e.get("query", ""),
                e.get("asset_tag", ""),
            ),
            "source_key": source_key(e.get("source", "")),
            "novelty_score": novelty,
            "duplicate_similarity": max_sim,
            "age_hours_now": age_hours,
            "decay_24h": decay_24h,
            "sentiment_abs": abs(sentiment),
            "event_intensity": (
                novelty
                * (1.0 + min(impact_hits, 3) / 3.0)
                * (0.50 + 0.50 * abs(sentiment))
            ),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(EVENT_ENRICHED, index=False, encoding="utf-8-sig")
    return df

# ---------------------------------------------------------------------
# REGIME DETECTION
# ---------------------------------------------------------------------

def latest_context_row() -> dict:
    if not MARKET_CONTEXT.exists():
        return {}
    try:
        df = pd.read_csv(MARKET_CONTEXT)
        if df.empty:
            return {}
        return df.iloc[-1].to_dict()
    except Exception:
        return {}

def get_num(row: dict, *names):
    for name in names:
        try:
            v = float(row.get(name))
            if np.isfinite(v):
                return v
        except Exception:
            pass
    return np.nan

def detect_regime(ctx: dict) -> dict:
    vix = get_num(ctx, "vix_close")
    spy20 = get_num(ctx, "spy_ret_20")
    qqq20 = get_num(ctx, "qqq_ret_20")
    copper20 = get_num(ctx, "hg_f_ret_20")
    usd20 = get_num(ctx, "uup_ret_20")
    fx20 = get_num(ctx, "clp_x_ret_20")
    us2 = get_num(ctx, "fred_us2y")
    us10 = get_num(ctx, "fred_us10y")

    risk = "NEUTRAL"
    if np.isfinite(vix) and vix >= 25:
        risk = "RISK_OFF"
    elif (
        np.isfinite(spy20) and spy20 < -0.06
    ) or (
        np.isfinite(qqq20) and qqq20 < -0.08
    ):
        risk = "RISK_OFF"
    elif (
        np.isfinite(vix) and vix < 18
        and np.isfinite(spy20) and spy20 > 0.02
    ):
        risk = "RISK_ON"

    commodity = "COMMODITY_NEUTRAL"
    if np.isfinite(copper20):
        if copper20 > 0.06:
            commodity = "COPPER_STRONG"
        elif copper20 < -0.06:
            commodity = "COPPER_WEAK"

    dollar = "USD_NEUTRAL"
    if np.isfinite(usd20):
        if usd20 > 0.025:
            dollar = "USD_STRONG"
        elif usd20 < -0.025:
            dollar = "USD_WEAK"

    chile_fx = "CLP_NEUTRAL"
    if np.isfinite(fx20):
        if fx20 > 0.03:
            chile_fx = "CLP_WEAK"
        elif fx20 < -0.03:
            chile_fx = "CLP_STRONG"

    curve = np.nan
    if np.isfinite(us10) and np.isfinite(us2):
        curve = us10 - us2

    regime = f"{risk}|{commodity}|{dollar}|{chile_fx}"

    return {
        "regime": regime,
        "risk_regime": risk,
        "commodity_regime": commodity,
        "dollar_regime": dollar,
        "chile_fx_regime": chile_fx,
        "vix": vix,
        "curve_10y_2y": curve,
    }

# ---------------------------------------------------------------------
# EVENT IMPACT LEARNING
# ---------------------------------------------------------------------

def join_enriched_outcomes(
    enriched: pd.DataFrame,
) -> pd.DataFrame:

    if enriched.empty or not EVENT_OUTCOMES.exists():
        return pd.DataFrame()

    # Primeros días del forward paper puede existir event_outcomes.csv
    # pero estar vacío (0 bytes o sin cabecera) porque todavía ninguna
    # noticia ha madurado a 1/5/20 sesiones. Eso NO es un error.
    try:
        if EVENT_OUTCOMES.stat().st_size == 0:
            return pd.DataFrame()
    except OSError:
        return pd.DataFrame()

    try:
        out = pd.read_csv(EVENT_OUTCOMES)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except Exception as e:
        print("  ADVERTENCIA: no se pudo leer event_outcomes.csv:", e)
        return pd.DataFrame()

    if out.empty or "event_id" not in out.columns:
        return pd.DataFrame()

    keep = [
        "event_id", "category", "novelty_score",
        "event_intensity", "source_key",
    ]
    available = [c for c in keep if c in enriched.columns]
    if "event_id" not in available:
        return pd.DataFrame()

    left = enriched[available].drop_duplicates("event_id")
    z = out.merge(left, on="event_id", how="left")
    return z

def impact_statistics(
    enriched: pd.DataFrame,
    regime: dict,
) -> pd.DataFrame:

    z = join_enriched_outcomes(enriched)
    if z.empty:
        pd.DataFrame().to_csv(EVENT_IMPACT, index=False)
        return pd.DataFrame()

    # Como el regime actual no estaba guardado históricamente en cada noticia
    # de v1.8, esta tabla inicial condiciona por categoría/activo/sentimiento.
    # v1.9 guardará régimen por ejecución para futuros eventos.
    groups = [
        "category",
        "evaluated_asset",
        "sentiment_bucket",
        "direct_match",
    ]

    rows = []
    for keys, g in z.groupby(groups, dropna=False):
        rec = dict(zip(groups, keys))
        rec["n_events"] = len(g)
        rec["mean_novelty"] = float(
            pd.to_numeric(g["novelty_score"], errors="coerce").mean()
        )
        rec["mean_intensity"] = float(
            pd.to_numeric(g["event_intensity"], errors="coerce").mean()
        )

        for h in [1, 5, 20]:
            r = pd.to_numeric(
                g.loc[g[f"matured_{h}s"] == 1, f"ret_{h}s"],
                errors="coerce",
            ).dropna()

            rec[f"n_{h}s"] = len(r)
            rec[f"mean_ret_{h}s"] = float(r.mean()) if len(r) else np.nan
            rec[f"median_ret_{h}s"] = float(r.median()) if len(r) else np.nan
            rec[f"positive_rate_{h}s"] = (
                float((r > 0).mean()) if len(r) else np.nan
            )

            # Shrinkage simple hacia cero; evita exagerar grupos pequeños.
            n = len(r)
            rec[f"shrunk_mean_ret_{h}s"] = (
                float(r.mean()) * (n / (n + 25.0))
                if n else 0.0
            )

        rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(EVENT_IMPACT, index=False, encoding="utf-8-sig")
    return df

def current_event_pressure(
    enriched: pd.DataFrame,
) -> pd.DataFrame:

    if enriched.empty:
        return pd.DataFrame()

    df = enriched.copy()
    df["retrieved_ts"] = pd.to_datetime(
        df["retrieved_at_utc"], errors="coerce", utc=True
    )
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)
    df = df[df["retrieved_ts"] >= cutoff]

    if df.empty:
        return pd.DataFrame()

    df["pressure"] = (
        pd.to_numeric(df["lexical_sentiment"], errors="coerce").fillna(0.0)
        * pd.to_numeric(df["event_intensity"], errors="coerce").fillna(0.0)
        * pd.to_numeric(df["decay_24h"], errors="coerce").fillna(0.0)
    )

    return (
        df.groupby(["asset_tag", "category"], dropna=False)
        .agg(
            event_count=("event_id", "count"),
            pressure=("pressure", "sum"),
            novelty=("novelty_score", "mean"),
            intensity=("event_intensity", "mean"),
        )
        .reset_index()
        .sort_values("pressure", ascending=False)
    )

# ---------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------

def age_hours(path: Path) -> float:
    if not path.exists():
        return float("inf")
    ts = datetime.fromtimestamp(
        path.stat().st_mtime,
        tz=timezone.utc,
    )
    return (
        datetime.now(timezone.utc) - ts
    ).total_seconds() / 3600.0

def health_check() -> dict:
    checks = {}

    files = {
        "v17_signals": V17_DIR / "current_signals.csv",
        "forward_ledger": FORWARD_DIR / "ledger.csv",
        "raw_events": RAW_EVENTS,
        "market_context": MARKET_CONTEXT,
        "event_outcomes": EVENT_OUTCOMES,
        "daily_report": DAILY_REPORT,
    }

    for name, path in files.items():
        checks[name] = {
            "exists": path.exists(),
            "age_hours": age_hours(path),
            "path": str(path.resolve()),
        }

    # Heurística simple de salud.
    critical = ["v17_signals", "forward_ledger", "raw_events", "market_context"]
    healthy = all(checks[x]["exists"] for x in critical)

    result = {
        "checked_at_utc": now_utc(),
        "healthy": healthy,
        "checks": checks,
        "v18_embedded_sha256": V18_SHA256,
    }

    MASTER.mkdir(exist_ok=True)
    HEALTH_FILE.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result

# ---------------------------------------------------------------------
# BACKUP
# ---------------------------------------------------------------------

def daily_backup():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    target = BACKUP_DIR / f"mfp3_backup_{stamp}.zip"

    if target.exists():
        return target

    candidates = [
        V17_DIR,
        FORWARD_DIR,
        EVENT_DIR,
        MASTER,
    ]

    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zf:
        for folder in candidates:
            if not folder.exists():
                continue
            for p in folder.rglob("*"):
                if not p.is_file():
                    continue
                # Evitar incluir backups dentro de backups.
                if BACKUP_DIR in p.parents:
                    continue
                zf.write(
                    p,
                    arcname=str(p.relative_to(ROOT)),
                )

    # Mantener últimos 7 backups.
    backups = sorted(BACKUP_DIR.glob("mfp3_backup_*.zip"))
    for old in backups[:-7]:
        try:
            old.unlink()
        except Exception:
            pass

    return target

# ---------------------------------------------------------------------
# WINDOWS TASK SCHEDULER
# ---------------------------------------------------------------------

def install_task():
    if os.name != "nt":
        raise SystemExit("--install sólo está preparado para Windows.")

    script = str(Path(__file__).resolve())
    python = str(Path(sys.executable).resolve())
    action = f'"{python}" "{script}"'

    # Diario: noticias también son relevantes en fines de semana.
    cmd = [
        "schtasks",
        "/Create",
        "/TN", TASK_NAME,
        "/TR", action,
        "/SC", "DAILY",
        "/ST", "18:30",
        "/F",
    ]

    print("Instalando tarea automática...")
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if p.returncode != 0:
        print(p.stdout)
        print(p.stderr)
        raise SystemExit(
            "No se pudo crear la tarea. "
            "Puedes ejecutar el archivo manualmente."
        )

    print(p.stdout.strip())
    print(
        "\nInstalado. Windows ejecutará este mismo archivo "
        "todos los días a las 18:30."
    )

def uninstall_task():
    if os.name != "nt":
        raise SystemExit("--uninstall sólo está preparado para Windows.")

    p = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print((p.stdout or p.stderr).strip())

# ---------------------------------------------------------------------
# RUN EMBEDDED v1.8
# ---------------------------------------------------------------------

def run_v18(full=False):
    old_argv = sys.argv[:]
    try:
        # v1.8 tiene su propio argparse.
        sys.argv = ["mfp3_onefile_v1_8_embedded.py"]
        if full:
            sys.argv.append("--full")

        g = {
            "__name__": "mfp3_onefile_v18_embedded",
            "__file__": "<embedded:v1.8>",
            "__builtins__": __builtins__,
        }
        exec(compile(V18_SOURCE, g["__file__"], "exec"), g, g)
        g["main"]()
    finally:
        sys.argv = old_argv

# ---------------------------------------------------------------------
# DAILY ADVANCED REPORT
# ---------------------------------------------------------------------

def advanced_report(
    enriched: pd.DataFrame,
    impact: pd.DataFrame,
    regime: dict,
    pressure: pd.DataFrame,
    health: dict,
):
    MASTER.mkdir(exist_ok=True)

    report = {
        "recorded_at_utc": now_utc(),
        "regime": regime.get("regime"),
        "risk_regime": regime.get("risk_regime"),
        "commodity_regime": regime.get("commodity_regime"),
        "dollar_regime": regime.get("dollar_regime"),
        "chile_fx_regime": regime.get("chile_fx_regime"),
        "events_enriched_total": len(enriched),
        "impact_groups": len(impact),
        "health_ok": health.get("healthy"),
        "v18_sha256": V18_SHA256,
    }

    if not pressure.empty:
        for tag in ["QQQ", "ECH", "CPER", "GLOBAL"]:
            z = pressure[pressure["asset_tag"] == tag]
            report[f"pressure_{tag.lower()}"] = (
                float(z["pressure"].sum()) if len(z) else 0.0
            )
            report[f"events48h_{tag.lower()}"] = (
                int(z["event_count"].sum()) if len(z) else 0
            )

    path = MASTER / "advanced_daily_report.csv"
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat(
            [old, pd.DataFrame([report])],
            ignore_index=True,
            sort=False,
        )
    else:
        new = pd.DataFrame([report])

    new.to_csv(path, index=False, encoding="utf-8-sig")
    return report

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()

    if args.install:
        install_task()
        return

    if args.uninstall:
        uninstall_task()
        return

    if args.health:
        h = health_check()
        print(json.dumps(h, indent=2, ensure_ascii=False))
        return

    if args.status:
        h = health_check()
        print("\nMFP-3 v1.9 STATUS")
        print("Healthy:", h["healthy"])
        for k, v in h["checks"].items():
            print(
                f"{k:18s} exists={v['exists']} "
                f"age={v['age_hours']:.1f}h"
            )
        return

    print("\n" + "=" * 92)
    print("MFP-3 ONE FILE v1.9.1 — AUTONOMOUS EVENT LEARNING")
    print("=" * 92)

    # Ejecutar sistema existente.
    run_v18(full=args.full)

    # Mejoras v1.9.
    print("\n[v1.9] Enriqueciendo noticias...")
    enriched = enrich_events()

    print("[v1.9] Detectando régimen...")
    ctx = latest_context_row()
    regime = detect_regime(ctx)

    print("[v1.9] Aprendiendo impacto por categoría...")
    impact = impact_statistics(enriched, regime)

    print("[v1.9] Calculando presión informativa 48h...")
    pressure = current_event_pressure(enriched)
    pressure_path = EVENT_DIR / "current_event_pressure.csv"
    pressure.to_csv(
        pressure_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("[v1.9] Health-check...")
    health = health_check()

    print("[v1.9] Backup...")
    backup = daily_backup()

    report = advanced_report(
        enriched, impact, regime, pressure, health
    )

    print("\n" + "=" * 92)
    print("RESUMEN v1.9")
    print("=" * 92)
    print("Régimen:", regime.get("regime"))
    print("Eventos enriquecidos:", len(enriched))
    print("Grupos de impacto:", len(impact))
    print("Health:", "OK" if health.get("healthy") else "REVISAR")
    print("Backup:", backup)

    if not pressure.empty:
        print("\nPresión informativa últimas 48h:")
        with pd.option_context(
            "display.max_rows", 20,
            "display.max_columns", None,
            "display.width", 170,
        ):
            print(pressure.head(20))

    print("\nUso diario:")
    print("  py mfp3_onefile_v1_9.py")
    print("\nInstalar ejecución automática:")
    print("  py mfp3_onefile_v1_9.py --install")
    print("\nNo ejecuta operaciones reales.")

if __name__ == "__main__":
    main()
