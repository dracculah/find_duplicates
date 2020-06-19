import os
import hashlib
import copy

DEBUG = False
SHOW_PROGRESS = False

class Settings:
	def __init__(self):
		self.hard_prove = False # will rerun every file and will check the whole content too (not just hash) (for equal suspects only)
		self.detect_changed_names = False # detect if the content is the same, but different dir or file names
		self.ignore_git = True # ignore ".git" dirs and below

def calcFileHash(fn):
	if SHOW_PROGRESS:
		print("hashing '{}'".format(fn))
	m = hashlib.md5()
	f = open(fn,mode='rb')
	while True:
		chunk = f.read(4096)
		if chunk:
			m.update(chunk)
		else:
			break
	f.close()
	str_digest = m.hexdigest()
	return str_digest

def calcStrHash(_str):
	m = hashlib.md5()
	m.update(_str.encode('utf-8'))
	str_digest = m.hexdigest()
	return str_digest

class TreeElem:
	def __init__(self,_root_dir,_parent_elem):
		self.root_dir = _root_dir; # how this dir is called
		if self.root_dir[-1] != '/':
			self.root_dir += "/"
		self.parent_elem = _parent_elem # parent element (if exists)
		self.childFiles = {} # dict of name and hash
		self.childDirs = {} # dict of name and obj
		self.strHash = ""
	def getFullPath(self):
		_str = "" + self.root_dir
		par = self.parent_elem;
		while (par != None):
			_str = par.root_dir + _str
			par = par.parent_elem
		if _str != "": # making DOUBLE sure
			if _str[-1] != '/':
				_str += "/"
		return _str
	def getHash(self):
		if DEBUG:
			print("DBG: requesting HASH from {} ({}) = '{}'".format(self.getFullPath(),self,self.strHash))
		return ""+self.strHash
	def reCalcHash(self):
		if DEBUG:
			print("DBG: recalc'ing HASH for DIR '{}' ({})".format(self.getFullPath(),self))
		_str = ""
		first = True
		for _d in self.childDirs.values():
			_s = ""
			if first == False:
				_s = ",'{}'".format(_d.getHash())
			else:
				_s = "'{}'".format(_d.getHash())
			_str += _s
			first = False
		for _f in self.childFiles.values():
			_s = ""
			if first == False:
				_s = ",'{}'".format(_f)
			else:
				_s = "'{}'".format(_f)
			_str += _s
			first = False
		_str = "[" + _str + "]"
		self.strHash = calcStrHash(_str)
		if DEBUG:
			print("DBG: just calc'ed HASH for {} ({}), {} -> '{}'".format(self.getFullPath(),self,_str,self.strHash))
		if self.parent_elem != None:
			self.parent_elem.reCalcHash()
	def addFile(self, fn):
		fullPath = self.getFullPath()
		str_hash = calcFileHash(fullPath+fn)
		if DEBUG:
			print("DBG: adding FILE '{}' -> '{}'".format(fn,str_hash))
		self.childFiles[fn] = str_hash
		assert(len(self.childFiles)>0)
		self.reCalcHash()
	def addDir(self, _dir, _fp):
		if DEBUG:
			print("DBG: adding DIR -> '{}' ({}), parent:{}".format(_dir,_fp,self.root_dir))
		newDir = TreeElem(_dir,self)
		self.childDirs[_dir] = newDir
		newDir.reCalcHash() # cascade recalcing Hashes up the hierarchy
		return newDir

def getTree(dirName, _parent_element, _setts):
	listOfFile = os.listdir(dirName)
	for entry in listOfFile:
		fullPath = os.path.join(dirName, entry)
		if os.path.isdir(fullPath):
			if entry == ".git":
				if _setts.ignore_git == True:
					continue
			childDir = _parent_element.addDir(entry,fullPath)
			getTree(fullPath, childDir, _setts)
		else:
			if not os.path.islink(fullPath):
				_parent_element.addFile(entry)
			
def add_a_tree(dirName, _setts):
	parent = TreeElem(dirName, None)
	getTree(dirName, parent, _setts)
	return parent

def hard_prove_files(fn1,fn2):
	if DEBUG or SHOW_PROGRESS:
		print("+-- hard proving '{}' == '{}'".format(fn1,fn2))
	f1 = open(fn1,"rb")
	f2 = open(fn2,"rb")
	while True:
		chunk1 = f1.read(4096)
		chunk2 = f2.read(4096)
		if len(chunk1) != len(chunk2):
			f1.close()
			f2.close()
			return False
		if ((not chunk1) or (not chunk2)):
			break
		idx = 0
		while idx < len(chunk1):
			if chunk1[idx] != chunk2[idx]:
				f1.close()
				f2.close()
				return False
			idx+=1
	f1.close()
	f2.close()
	return True

def hard_prove_dirs(_n1,_n2,_setts):
	if len(_n1.childFiles) != len(_n2.childFiles):
		return False
	if len(_n1.childDirs) != len(_n2.childDirs):
		return False
	fullPath1 = _n1.getFullPath()
	fullPath2 = _n2.getFullPath()
	for _f in _n1.childFiles:
		fn1 = fullPath1 + _f
		fn2 = fullPath2 + _f
		if fn1 != fn2:
			hard_prove_files(fn1, fn2)
	for _d in _n1.childDirs:
		if _setts.detect_changed_names == False:
			_child_n1 = _n1.childDirs[_d]
			_child_n2 = _n2.childDirs[_d]
			res = hard_prove_dirs(_child_n1,_child_n2,_setts)
			if res == False:
				return False
		else:
			_child_n1 = _n1.childDirs[_d]
			_dir_hash = _child_n1.getHash()
			# find the one with the same hash, but diff name
			for _x in _n2.childDirs:
				if _n2.childDirs[_x].getHash() == _dir_hash:
					_child_n2 = _n2.childDirs[_d]
					res = hard_prove_dirs(_child_n1,_child_n2,_setts)
					if res == False:
						return False
					else:
						if _x != _d: # not same (sub)name
							print("--- EQUAL DIRS, but CHANGED NAME '{}' == '{}'".format(_child_n1.getFullPath(),_child_n2.getFullPath()))
	return True

def hard_prove_dirs_are_equal(_n1,_n2,_setts):
	res = hard_prove_dirs(_n1,_n2,_setts)
	return res

def check_files(_n1, _n2, _setts):
	for _f1 in _n1.childFiles:
		for _f2 in _n2.childFiles:
			if _n1.childFiles[_f1] == _n2.childFiles[_f2]: # equal hashes
				fn1 = _n1.getFullPath()+_f1
				fn2 = _n2.getFullPath()+_f2
				if fn1 != fn2: # not same file
					hard = False
					if _setts.hard_prove:
						hard = hard_prove_files(fn1, fn2)
					else:
						hard = True
					if hard == True:
						print("--- equal files '{}' == '{}'".format(fn1,fn2))

def check_single_values(_n1, _n2, check_if_same, _setts):
	fullPath1 = _n1.getFullPath()
	fullPath2 = _n2.getFullPath()
	if DEBUG:
		print("DBG: DIR compare '{}' <> '{}'".format(fullPath1, fullPath2))
	if check_if_same == True:
		# check if same
		if fullPath1 == fullPath2:
			if DEBUG:
				print("DBG: DIR SAME '{}' == '{}'".format(fullPath1, fullPath2))
			return False
	hash1 = _n1.getHash()
	hash2 = _n2.getHash()
	if hash1 == hash2:
		hard = False
		if _setts.hard_prove:
			hard = hard_prove_dirs_are_equal(_n1, _n2, _setts)
		else:
			hard = True
		if hard == True:
			if DEBUG == True:
				print("--- EQUAL DIRS: {} == {} // (hash: '{}')".format(fullPath1,fullPath2,hash1))
			else:
				print("--- EQUAL DIRS: '{}' == '{}'".format(fullPath1,fullPath2))
		return True
	if DEBUG:
		print("DBG: DIR NOT EQUAL '{}' ({}) != '{}' ({})".format(fullPath1,hash1,fullPath2,hash2))
	check_files(_n1, _n2, _setts)
	return False

def run_normal_recursion(_node1, _node2, check_if_same, _setts): # here _node1 will be just a ref (static) and _node2 iterated
	check_single_values(_node1, _node2, check_if_same, _setts)
	for _n2 in _node2.childDirs.values():
		check_single_values(_node1, _n2, check_if_same, _setts)
		run_normal_recursion(_node1, _n2, check_if_same, _setts)

def run_2D_recursion(_node1, _node2, check_if_same, _setts): # here _node1 will be iterated and _node2 just a ref (static)
	run_normal_recursion(_node1, _node2, check_if_same, _setts)
	for _n1 in _node1.childDirs.values():
		run_normal_recursion(_n1, _node2, check_if_same, _setts)
		run_2D_recursion(_n1, _node2, check_if_same, _setts)

def compare_two_trees(_t1,_t2,check_if_same, _setts):
	# now let's compare O(n^2) dir nodes (except same ones if 'check_if_same' is set)
	# oh yeah, will do a 2-D recursion ^^
	run_2D_recursion(_t1,_t2,check_if_same, _setts)

def compare_within_tree(parent_tree_elem, _setts):
	# let's make a deep copy
	copy_tree_elem = copy.deepcopy(parent_tree_elem)
	# now compare as they were seperate, except lookout for same ones
	compare_two_trees(parent_tree_elem, copy_tree_elem, True, _setts)

def find_duplicates_within_tree(dirN, _setts):
	tree1 = add_a_tree(dirN, _setts)
	# check within tree1
	compare_within_tree(tree1, _setts)

def find_duplicates_with_two_trees(dirN1, dirN2, _setts):
	tree1 = add_a_tree(dirN1, _setts)
	tree2 = add_a_tree(dirN2, _setts)
	# check within tree1
	compare_within_tree(tree1, _setts)
	# check within tree2
	compare_within_tree(tree2, _setts)
	# compare the 2 trees now
	compare_two_trees(tree1, tree2, True, _setts) # when we don't add the same path it will be False here
	
setts = Settings()
setts.hard_prove = False # if true compares the whole content is equal, not just hash
setts.detect_changed_names = False # for dirs only: if true can detect same dirs with changed names
setts.ignore_git = True # if true ignores ".git" dir and below
#find_duplicates_within_tree("~your~dir", setts) # finds duplicates within a single tree only
#find_duplicates_with_two_trees("~your~dir~1", "~your~dir~2", setts) # compares every tree individually and then compares the two trees
