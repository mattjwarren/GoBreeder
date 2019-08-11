import random
import vm
import hashlib
class CircularList(object):
    '''post increment circular list'''
    def __init__(self):
        self.values=list() #list
        self._ptr=None
        self._direction=1        
    
    def __contains__(self,n):
        return n in self.values
    
    def __iter__(self):
        return self
    
    def __str__(self):
        if self._direction<0:
            direction='<'
        else:
            direction='>'
        return direction+str(self._ptr)+str(self.values)
    
    def next(self):
        return self.get()
        
    def _post_increment(self):
        self._ptr+=self._direction
        if self._ptr<0:
            self._ptr=len(self.values)-1
        elif self._ptr>len(self.values)-1:
            self._ptr=0
                               
    def reverse(self):
        self._direction=-self._direction
        
    def get(self):#generate?
        if len(self.values)>0:
            value=self.values[self._ptr]
            self._post_increment()
            return value #yield()?
        else:
            return None    #None?
       
    def set_values(self,values):
        self.values=values
        self._ptr=0
        self._direction=1
       
    def set(self,value):
        self.values[self._ptr]=value
        self._post_increment()
        
    def add_value(self,value):
        if self._ptr==None:
            self._ptr=0
        self.values.append(value)
        
    def __add__(self,other):
        '''cl1(ptr/dir)+cl2(ptr/dir)=cl3(0/1) (notice: the pointers, not the values. ofc the values get added) '''
        new_values=self.values+other.values
        self.__init__()
        self.set_values(new_values)
        return self
        
        
        
        #put me somewhere else   //.. use the right thing, luke
def weighted_choice(choices):
    total = sum(w for c, w in choices)
    r = random.uniform(0, total)
    upto = 0
    for c, w in choices:
        if upto + w > r:
            return c
        upto += w
          
class GoGenome(object):
    max_size=1024
    
    def __str__(self):
        return self.hashname
        

    def __init__(self,dna=None):
        self.evaluated=False
        if not dna:
            self.genesis()
        else:
            self.dna = dna
        self.hashname=hashlib.sha512(repr(self.dna)).hexdigest()[:64]    #we'll try this till we get collisions ;p
        
    def __getitem__(self,idx):
        return self.dna[idx]
    
    def __len__(self):
        return len(self.dna)
        
    def mutate(self,idx):
        #types of mutation and their weights
        #mute types
        #  0   completely new op
        #  1   op swap #current index independent (disruptive mutation, relatively)
        #  2   local (1%) diffusion of data member
        
        # Not Implemented Yet (indeices may not be correct, refer to implementation)
        
        #  1    data A jump
        #  2   data B jump 
        #  3    both data jump
        #  4  A jitter
        #  5  B jitter
        #  6    both jitter
        #  7 - copy nearby op (replace) and re-mute. if already re-mtuing, leave alone
        #  8 - diffuse.  mix elements from nearby ops amongst nearby ops
        #  9 insert a new instruction
        #  10 insert a number 7 rather than replace.
        #  11 delete a genome insert a new one elsewhere
        
        choices=range(0,1) #extend as needed...
        weights=[2,1]#,1] extend as needed
        choices=zip(choices,weights)
        mutation=weighted_choice(choices)
        
        if mutation==0: #weight 1
            #completely new op
            new_dna=self.generate_dna()
            self.dna[idx]=new_dna
        
        #not implemented
        
        ###################  opcodes={'add':    [['A','B']  ,10],
        #broken !!!!!!!!!!!!!!!!!!!
        ############################################cutout for now again. grr
        elif mutation==1:
            #data jitter by int(-1..1)
            if self.dna[idx][1][0] is not None:
                first=str(self.dna[idx][1][0])[0]
                if first in '0123456789-':
                    #is about first char of int type data values always being 0-9,-
                    self.dna[idx][1][0]=str(int(self.dna[idx][1][0])+(random.randint(0,2)-1))
            if self.dna[idx][1][1] is not None:
                first=str(self.dna[idx][1][1])[0]
                if first in '0123456789-':
                    self.dna[idx][1][1]=str(int(self.dna[idx][1][1])+(random.randint(0,2)-1))

                
#             #swap ops
#             idx_a,idx_b=0,0
#             while idx_a==idx_b:#rare but will happen
#                 idx_a=random.randint(0,len(self.dna))
#                 idx_b=random.randint(0,len(self.dna))
#             self.dna[idx_a],self.dna[idx_b]=self.dna[idx_b],self.dna[idx_a]
#             
#             
#             #TODO:
#             ##Need to think this through to handle swapping to/from opcode that hhave no data members
            
#        elif mutation==2: #weight 1
#            #local diffusion : data swap between nearby (len/100) =1%
#            slot_to_swap=random.choice([0,1]) #0=A 1=B
#            
#            #could do this just by using randint but 
#            #this came first...
#            diffusion_width=(len(self.dna)/100)/2
#            diffusion_range=range(-diffusion_width,diffusion_width+1)
#            op_to_swap=random.choice(diffusion_range)
#            
#            if op_to_swap==0: return #swapping with ourself
#            
#            op_swap_index=(idx+op_to_swap) % len(self.dna) #wraparound the index
#            current_op=self.dna[idx]
#            self.dna[idx][1][slot_to_swap]=self.dna[op_swap_index][1][slot_to_swap]
#            self.dna[op_swap_index][1][slot_to_swap]=current_op[1][slot_to_swap]
            
        
    def genesis(self):
        genome_length=GoGenome.max_size
        #putting this seed DNA here helped jumpstart the pop evolution.
        #without it, it takes a long time to ignite the fire.
        # however, other sparks may do better...
        
        #turns out the spark colours the fire a lot! esp if spark is small and simple..
        
        self.dna=[  ('sstn',['1','1']),             #stone cursor to 1,1
                    ('mov',['STN_C_STATS','RES']),  #stone state into RES
                    ('cmpne',['RES','0']),          #if its not 0
                    ('jmprl',['4']),                #jump to next stone
                    ('mov',['STN_C_XCOORD','X']),   #else set x,y to empty stone
                    ('mov',['STN_C_YCOORD','Y']),
                    ('jmp',['250']),                #jump 'somewhere'
                    ('sstn',['2','2']),             #'NEXT STONE' stone cursor to 1,1
                    ('mov',['STN_C_STATS','RES']),  #stone state into RES
                    ('cmpne',['RES','0']),          #if its not 0
                    ('jmpr',['4']),                 #jump to ..... past end of this block
                    ('mov',['STN_C_XCOORD','X']),   #else set x,y to empty stone
                    ('mov',['STN_C_YCOORD','Y'])
                    ]                               #then continue whatver crazy shennanigns
        
        genome_length-=len(self.dna)
        while genome_length>0:
            new_dna=self.generate_dna()
            self.dna.append(new_dna)
            genome_length-=1
    
    def generate_dna(self):
        #        opcode     operands   random choice weight
        opcodes={'add':    [['A','B']  ,10],
                 'sub':    [['A','B']  ,10],
                 'incr':   [[]         ,10],
                 'decr':   [[]         ,10],
                 'mul':    [['A','B']  ,3],
                 'div':    [['A','B']  ,3],
                 'cmpe':   [['A','B']  ,1],
                 'cmpne':  [['A','B']  ,1],
                 'cmp0':   [['A']      ,1],
                 'cmplt':  [['A','B']  ,1],
                 'cmpgt':  [['A','B']  ,1],
                 'and':    [['A','B']  ,1],
                 'or':     [['A','B']  ,1],
                 'not':    [['A']      ,1],
                 'xor':    [['A','B']  ,1],
                 'jmp':    [['A']      ,1],
                 'jmpr':   [['A']      ,1],
                 'jmp0':   [['A']      ,1],
                 'jmpl':   [['A']      ,1],
                 'jmprl':  [['A']      ,1],
                 'jmpr0':  [['A']      ,1],
                 'call':   [['A']      ,1],
                 'callr':  [['A']      ,1],
                 'call0':  [['A']      ,1],
                 'callr0': [['A']      ,1],
                 'calll':  [['A']      ,1],
                 'callrl': [['A']      ,1],
                 'ret':    [[]         ,1],
                 'ret0':   [[]         ,1],
                 'retl':   [[]         ,1],
                 'mov':    [['A','B']  ,30],
                 'push':   [['A']      ,3],
                 'pop':    [[]         ,3],
                 'sstn':   [['A','B']  ,6],
                 'nstn':   [[]         ,3],
                 'rstn':   [[]         ,3],
                 'nblk':   [[]         ,3],
                 'nwht':   [[]         ,3],
                 'rwht':   [[]         ,3],
                 'nfrn':   [[]         ,3],
                 'rfrn':   [[]         ,3],
                 'nnme':   [[]         ,3],
                 'rnme':   [[]         ,3],
                 'nspc':   [[]         ,3],
                 'rspc':   [[]         ,3],
                 'nblkf':  [[]         ,3],
                 'rblkf':  [[]         ,3],
                 'nwhtf':  [[]         ,3],
                 'rwhtf':  [[]         ,3],
                 'nfrnf':  [[]         ,3],
                 'rfrnf':  [[]         ,3],
                 'nnmef':  [[]         ,3],
                 'rnmef':  [[]         ,3],
                 'iwxy':   [[]         ,3],
                 'dwxy':   [[]         ,3],
                 'rnd':    [[]         ,3]####aah the first element is the list
                     }
        
        board_pointers=['TL','TT','TR','ML','C','MR','BL','BB','BR']
        stn_ops=['STATS','XCOORD','YCOORD']

        #create a random genome string
        
        
        instruction_points=opcodes.keys()
        instruction_points=[ (key,opcodes[key][1]) for key in instruction_points ]
        
        do_not_modify=vm.GoVM.special_info_registers+['WXY']
        DO_NOT_MODIFY=False
        #get instruction
        instruction=weighted_choice(instruction_points)
        data_choices=opcodes[instruction][0]
        
        #whats really going on hhere, hows it breaking down
        
        #choose data from appropriate data points
        data={'A':None,'B':None}
        choices={}
        
        #I have no idea how this works, but I do remember its much better than the first try
        if instruction=='mov':
            choices['A']=vm.GoVM.general_purpose_registers+vm.GoVM.special_info_registers+vm.GoVM.stn_registers
            A_weights=vm.GoVM.general_purpose_weights+vm.GoVM.special_info_weights+vm.GoVM.stn_weights
            choices['A']=zip(choices['A'],A_weights)
            
            choices['B']=vm.GoVM.general_purpose_registers
            B_weights=vm.GoVM.general_purpose_weights
            choices['B']=zip(choices['B'],B_weights)
            
        elif instruction in vm.GoVM.branching_instructions:
            choices['A']=vm.GoVM.general_purpose_registers
            A_weights=vm.GoVM.general_purpose_weights
            choices['A']=zip(choices['A'],A_weights)
            
        else:
            choices['A']=vm.GoVM.general_purpose_registers+vm.GoVM.special_info_registers+vm.GoVM.stn_registers
            A_weights=vm.GoVM.general_purpose_weights+vm.GoVM.special_info_weights+vm.GoVM.stn_weights
            choices['A']=zip(choices['A'],A_weights)
            choices['B']=vm.GoVM.general_purpose_registers+vm.GoVM.special_info_registers+vm.GoVM.stn_registers
            B_weights=vm.GoVM.general_purpose_weights+vm.GoVM.special_info_weights+vm.GoVM.stn_weights
            choices['B']=zip(choices['B'],B_weights)
            
        for data_point in data_choices:
            choice=random.choice(['constant',weighted_choice(choices[data_point])])
            if choice=='constant': choice=random.randrange(0,8192)#ooohh a magic number
            if choice=='STN':
                choice='_'.join([choice,random.choice(board_pointers),random.choice(stn_ops)])
                DO_NOT_MODIFY=True
                #|
            if (choice not in do_not_modify) and (not DO_NOT_MODIFY):
                access_modifier=random.choice(['','m','*'])
            else:
                access_modifier=''
            data[data_point]=access_modifier+str(choice)
        
        return  (instruction,[data['A'],data['B']]) 

    def render(self):
        for opcode,opdata in self.dna:
            print opcode,opdata    
    
    
    