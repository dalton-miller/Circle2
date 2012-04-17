#
#   RSA.py : RSA encryption/decryption
# 
#  Part of the Python Cryptography Toolkit, version 1.1
# 
# Distribute and use freely; there are no restrictions on further 
# dissemination and usage except those imposed by the laws of your 
# country of residence.  This software is provided "as is" without
# warranty of fitness for use or suitability for any purpose, express
# or implied. Use at your own risk or not at all. 
# 

import pubkey
import number

error = 'RSA module'

# Generate an RSA key with N bits
def generate(nbits, randfunc, progress_func=None):
    obj=RSAobj()

    # Throughout this function, the idiom `(expr + 7) >> 3' is used to get
    # ceil(expr / 8).
    p_wanted_nbits = (nbits >> 1)
    pstr_wanted_len = (p_wanted_nbits + 7) >> 3
    qstr_wanted_len = ((nbits >> 1) + 7 - 3 + 3 + 17 + 7) >> 3
    # + 7 for the maximum value of difference;
    # - 3 for the foo handling below;
    # + 3 for the value of difference;
    # + 17 for the value of e_start;
    # + 7 for round-up division by 8.
    
    rand_str = randfunc(pstr_wanted_len + qstr_wanted_len)
    p_str = rand_str[:pstr_wanted_len]
    q_str_high = rand_str[pstr_wanted_len:-3]

    # Recycle a few bits.  For justification, see comments in getPrimeFromLong,
    # especially the last paragraph.
    q_low_byte = ord(rand_str[-3])
    q_low_byte ^= (q_low_byte >> 1)
    q_low_byte ^= (ord(p_str[-1]) >> 2)
    
    # p is from the first (nbits>>1) bits of p_str.
    # q is from the first ((nbits>>1) + difference) bits of
    # (q_str_high + chr(q_low_byte)), where difference in [0, 7].
    # difference is from bits [nbits>>1, (nbits>>1) + 3) of rand_str.

    # Use the low 17+3 bits for e_start and difference.
    exp_diff = (ord(rand_str[-1])
                + (ord(rand_str[-2]) << 8)
                + (ord(rand_str[-3]) << 16))
    difference = exp_diff & 7
    e_start = (exp_diff >> 3) & ((1 << 17) - 1)

    p_discard_nbits = (pstr_wanted_len << 3) - p_wanted_nbits
    p_start = number.bytestolong(p_str) >> p_discard_nbits

    q_wanted_nbits = (nbits >> 1) + difference
    q_discard_nbits = ((qstr_wanted_len - 2) << 3) - q_wanted_nbits
    q_start = number.bytestolong(q_str_high + chr(q_low_byte)) >> q_discard_nbits
    
    
    # Generate the prime factors of n
    if progress_func: apply(progress_func, ('p\n',))
    obj.p=pubkey.getPrimeFromLong(p_start)
    if progress_func: apply(progress_func, ('q\n',))
    obj.q=pubkey.getPrimeFromLong(q_start)
    obj.n=obj.p*obj.q
    # Generate encryption exponent
    if progress_func: apply(progress_func, ('e\n',))
    obj.e=pubkey.getPrimeFromLong(long(e_start))
    if progress_func: apply(progress_func, ('d\n',))
    obj.d=pubkey.inverse(obj.e, (obj.p-1)*(obj.q-1))
    return obj

# Construct an RSA object
def construct(tuple):
    obj=RSAobj()
    if len(tuple) not in [2,3,5]:
        raise error, 'argument for construct() wrong length' 
    for i in range(len(tuple)):
	field = obj.keydata[i]
	setattr(obj, field, tuple[i])
    return obj

# Deconstruct an RSA object
def deconstruct(obj):
    tuple = ( )
    for i in range(5):
        field = obj.keydata[i]
        if not hasattr(obj,field):
	    break
        tuple = tuple + (getattr(obj, field),)
    return tuple


class RSAobj(pubkey.pubkey):
    keydata=['n', 'e', 'd', 'p','q']
    def _encrypt(self, plaintext, K=''):
    	if self.n<=plaintext:
	    raise error, 'Plaintext too large'
	return (pow(plaintext, self.e, self.n),)

    def _decrypt(self, ciphertext):
	if (not hasattr(self, 'd')):
	    raise error, 'Private key not available in this object'
	if self.n<=ciphertext[0]:
	    raise error, 'Ciphertext too large'
	return pow(ciphertext[0], self.d, self.n)

    def _sign(self, M, K=''):
	return (self._decrypt((M,)),)
    def _verify(self, M, sig):
	m2=self._encrypt(sig[0])
	if m2[0]==M: return 1
	else: return 0
	
    def size(self):
	"Return the maximum number of bits that can be handled by this key."
        bits, power = 0,1L
	while (power<self.n): bits, power = bits+1, power<<1
	return bits-1
	
    def hasprivate(self):
	"""Return a Boolean denoting whether the object contains
	private components."""
	if hasattr(self, 'd'): return 1
	else: return 0

    def publickey(self):
	"""Return a new key object containing only the public information."""
        return construct((self.n, self.e))
	

object = RSAobj


