import math

def rgb_to_lab (inputColor):
   num = 0
   RGB = [0, 0, 0]

   for value in inputColor :
       value = float(value) / 255

       if value > 0.04045 :
           value = ( ( value + 0.055 ) / 1.055 ) ** 2.4
       else :
           value = value / 12.92

       RGB[num] = value * 100
       num = num + 1

   X = RGB [0] * 0.4124 + RGB [1] * 0.3576 + RGB [2] * 0.1805
   Y = RGB [0] * 0.2126 + RGB [1] * 0.7152 + RGB [2] * 0.0722
   Z = RGB [0] * 0.0193 + RGB [1] * 0.1192 + RGB [2] * 0.9505
   XYZ = [X, Y, Z]

   XYZ[ 0 ] = float( XYZ[ 0 ] ) / 95.047         # ref_X =  95.047   Observer= 2°, Illuminant= D65
   XYZ[ 1 ] = float( XYZ[ 1 ] ) / 100.0          # ref_Y = 100.000
   XYZ[ 2 ] = float( XYZ[ 2 ] ) / 108.883        # ref_Z = 108.883

   num = 0
   for value in XYZ :

       if value > 0.008856 :
           value = value ** ( 0.3333333333333333 )
       else :
           value = ( 7.787 * value ) + ( 16 / 116 )

       XYZ[num] = value
       num = num + 1

   L = ( 116 * XYZ[ 1 ] ) - 16
   a = 500 * ( XYZ[ 0 ] - XYZ[ 1 ] )
   b = 200 * ( XYZ[ 1 ] - XYZ[ 2 ] )

   return [L, a, b]


def euclidean_dist(col1, col2):
    return math.sqrt(sum((v1 - v2)**2 for v1, v2 in zip(col1, col2)))

def color_parse_hex(hexcol):
    if hexcol[0] == '#':
        hexcol = hexcol[1:]
    if len(hexcol) == 6:
        return (int(hexcol[0:2], 16), int(hexcol[2:4], 16), int(hexcol[4:6], 16))
    elif len(hexcol) == 3:
        return (int(hexcol[0] * 2, 16), int(hexcol[1] * 2, 16), int(hexcol[2] * 2, 16))
    else:
        raise ValueError("Incorrect hex length")

def fmod(a, b):
    """Floating point remainder / modulo"""
    return (a - b * int(a / b)) % b if b else a

def rgb_to_hsv(rgb):
    r, g, b = rgb
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx - mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = fmod(60 * ((g - b) / df), 360)
    elif mx == g:
        h = fmod(60 * ((b - r) / df) + 120, 360)
    elif mx == b:
        h = fmod(60 * ((r - g) / df) + 240, 360)
    else:
        h = 0
    if mx == 0:
        s = 0
    else:
        s = df / mx
    v = mx
    return h, s, v

def hsv_to_rgb(hsv):
    h, s, v = hsv
    h = float(h)
    h = fmod(h, 360)
    s = float(s)
    v = float(v)
    h60 = h / 60.0
    h60f = math.floor(h60)
    hi = int(h60f) % 6
    f = h60 - h60f
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = 0, 0, 0
    if hi == 0:
        r, g, b = v, t, p
    elif hi == 1:
        r, g, b = q, v, p
    elif hi == 2:
        r, g, b = p, v, t
    elif hi == 3:
        r, g, b = p, q, v
    elif hi == 4:
        r, g, b = t, p, v
    elif hi == 5:
        r, g, b = v, p, q
    r, g, b = int(r * 255), int(g * 255), int(b * 255)
    return r, g, b

def hsv_to_hsl(hsv):
    h, s, v = hsv
    l = v * (1 - s / 2)
    new_s = 0 if l == 0 or l == 1 else (v - l) / min(l, 1 - l)
    return (h, new_s, l)

def hsl_to_hsv(hsl):
    h, s, l = hsl
    v = l + s * min(l, 1 - l)
    new_s = 0 if v == 0 else 2 * (1 - l / v)
    return (h, new_s, v) 

def rgb_to_hsl(rgb):
    return hsv_to_hsl(rgb_to_hsv(rgb))

def hsl_to_rgb(hsl):
    return hsv_to_rgb(hsl_to_hsv(hsl))

