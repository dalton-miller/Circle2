#
#   number.py : Number-theoretic functions 
# 
#  Part of the Python Cryptography Toolkit, version 1.1
# 
# Distribute and use freely; there are no restrictions on further 
# dissemination and usage except those imposed by the laws of your 
# country of residence.  This software is provided "as is" without
# warranty of fitness for use or suitability for any purpose, express
# or implied. Use at your own risk or not at all. 
# 

# Removed 31/12/01 pfh
#bignum = long
#try:
#    import gmp
#except ImportError:
#    try:
#        import mpz
#        #bignum=mpz.mpz       # Temporarily disabled; the 'outrageous exponent'
#                             # error messes things up.
#    except ImportError: 
#	pass

# Commented out and replaced with faster versions below
## def long2str(n):
##     s=''
##     while n>0:
##         s=chr(n & 255)+s
##         n=n>>8
##     return s

## import types
## def str2long(s):
##     if type(s)!=types.StringType: return s   # Integers will be left alone
##     return reduce(lambda x,y : x*256+ord(y), s, 0L)

if 0:  # This function is no longer used, at the time of writing.
 def getRandomNumber(N, randfunc):
    """Return an N-bit random number.  More precisely, pick a number from the
       range [0, 2**N) using a uniform distribution."""
    
    nbytes = N >> 3
    nbits = N & 7
    if nbits == 0:
        str = randfunc(nbytes)
    else:
        str = randfunc(nbytes + 1)
        str[0] = chr(ord(str[0]) >> (8 - nbits))
    return str2long(str)
    
def GCD(x,y):
    "Return the GCD of x and y."
    if x<0: x=-x
    if y<0: y=-y
    while x>0: x,y = y%x, x
    return y

def inverse(u, v):
    "Return the inverse of u mod v."
    u3, v3 = long(u), long(v)
    u1, v1 = 1L, 0L
    while v3>0:
	q=u3/v3
	u1, v1 = v1, u1-v1*q
	u3, v3 = v3, u3-v3*q
    while u1<0: u1=u1+v
    return u1
    
# Given a number of bits to generate and a random generation function,
# find a prime number of the appropriate size.

if 0:  # This function is no longer used, at the time of writing.
 def getPrime(N, randfunc):
    """Return a random N-bit prime number.  "N-bit" is used a bit loosely
       here; it can return any prime number between 3 and the lowest prime
       greater than or equal to (2**N - 1)."""
    
    number=getRandomNumber(N, randfunc) | 1
    while (not isPrime(number)):
        number=number+2
    return number


def getPrimeFromLong(raw):
    """Return the smallest prime number greater than or equal to (raw | 1)."""
    
    # Note that getPrime and getPrimeFromLong waste some of the bits
    # when searching for a prime: if A is a prime and B is the smallest
    # prime greater than A, then any value of raw in the range (A + 1, B]
    # will result in the same number B being returned.  This is a waste of
    # lg(B - A) bits.  In the vicinity of 2**510, the gap between successive
    # primes averages around 350 (according to a test script that loops around
    # getPrimeFromLong), thus wasting over 8 bits.  (More generally, the prime
    # number theorem suggests that in the vicinity of 2**n, the distance
    # between successive primes is about n*ln(2), so wasting about lg(n) - 0.5
    # bits.)
    #
    # (Similar numbers result if you consider the number of wasted bits to be
    # n minus the lg of the number of distinct prime numbers that can be
    # returned from this routine for values of raw between 0 and 2**n.)
    #
    # About the simplest counter-measure would be to append '\x01' to the
    # string from which raw is created, i.e. pre-multiply raw by 256.
    #
    # (Slightly more sophisticated is to shift raw by logb(logb(raw)) instead
    # of a constant shift of 8; where logb(x) = floor(lg(x)), as in libc.)
    #
    # Pre-shifting by 8 or 9 won't reduce the number of wasted bits to 0.
    # Pre-shifting by an overestimate of the inter-prime gap in the vicinity
    # of the result (e.g. appending '\x00\x01' to the string, thus pre-shifting
    # by 16) would reduce the wastage to about 0; though any pre-shifting must
    # be weighed against the extra cost of arithmetic with longer keys, or
    # conversely against the cost of filling the shifted bits from the random
    # source instead of with zeroes.
    #
    # However, as you can see from the first statement below, it's always safe
    # for the lowest bit of raw to be non-random.
    
    num = raw | 1
    while not isPrime(num):
        num += 2
    return num

def isPrime(N):
    "Return true if N is prime."
    if N in sieve: return 1
    for i in sieve:
        if (N % i)==0: return 0

    # Compute the highest bit that's set in N
    N1=N - 1L ; n=1L
    while (n<N): n=n<<1L 
    n = n >> 1L

    # Rabin-Miller test
    for c in sieve[:7]:
        a=long(c) ; d=1L ; t=n
        while (t):  # Iterate over the bits in N1
            x=(d*d) % N
            if x==1L and d!=1L and d!=N1: return 0  # Square root of 1 found
            if N1 & t: d=(x*a) % N
            else: d=x
            t = t >> 1L
        if d!=1L: return 0
    return 1

# Small primes used for checking primality; these are all the primes
# less than 256.  This should be enough to eliminate most of the odd
# numbers before needing to do a Rabin-Miller test at all.

sieve=[2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59,
       61, 67, 71, 73, 79, 83, 89, 97, 101, 103, 107, 109, 113, 127,
       131, 137, 139, 149, 151, 157, 163, 167, 173, 179, 181, 191]


# Improved conversion functions contributed by Barry Warsaw, after
# careful benchmarking  

import struct

def longtobytes(n, blocksize=0):
    """Convert a long integer to a byte string

    If optional blocksize is given and greater than zero, pad the front of the
    byte string with binary zeros so that the length is a multiple of
    blocksize.
    """
    # after much testing, this algorithm was deemed to be the fastest
    s = ''
    pack = struct.pack
    while n > 0:
        s = pack('>I', n & 0xffffffffL) + s
        n = n >> 32
    # strip off leading zeros
    for i in range(len(s)):
        if s[i] <> '\000':
            break
    else:
        # only happens when n == 0
        s = '\000'
        i = 0
    s = s[i:]
    # add back some pad bytes.  this could be done more efficiently w.r.t. the
    # de-padding being done above, but sigh...
    if blocksize > 0 and len(s) % blocksize:
        s = (blocksize - len(s) % blocksize) * '\000' + s
    return s

def bytestolong(s):
    """Convert a byte string to a long integer.

    This is (essentially) the inverse of longtobytes().
    """
    acc = 0L
    unpack = struct.unpack
    length = len(s)
    if length % 4:
        extra = (4 - length % 4)
        s = '\000' * extra + s
        length = length + extra
    for i in range(0, length, 4):
        acc = (acc << 32) + unpack('>I', s[i:i+4])[0]
    return acc

# For backwards compatibility...
long2str = longtobytes
str2long = bytestolong


# Local Variables:
# py-indent-offset:4
# End:
# vim: expandtab:shiftwidth=4 :
