'''
Created on 4 Sep 2013

@author: GB108544
'''
import sys

import board_info
import data_structures
import config
#from graphics import *
import random
import datetime

logging=False
def log(message):
    if logging:
        print message

class GoVM(object):
    working_X_registers=[ 'X'+str(N) for N in range(0,8) ] #change in gogenmoe to
    working_Y_registers=[ 'Y'+str(N) for N in range(0,8) ]
    general_working_registers=[ 'GP'+str(N) for N in range(0,8) ] #change in gogenmoe to

    board_pointers=['TL','TT','TR','ML','C','MR','BL','BB','BR']
    board_pointer_offsets={'TL':(-1,-1),
                           'TT':(0,-1),
                           'TR':(1,-1),
                           'ML':(-1,0),
                           'C' :(0,0),
                           'MR':(1,0),
                           'BL':(-1,1),
                           'BB':(0,1),
                           'BR':(1,1)
                           }         
    
    ####
    #can accept arbitrary values
    general_purpose_registers=working_X_registers+working_Y_registers
    general_purpose_weights=[1]*len(general_purpose_registers)

    general_purpose_registers+=['RES','X','Y','WXY']
    general_purpose_weights+=[1,1,1,1]#are the wieght definitions in the right place? breeder maybe? the VM shouldn't care about it.
    
    
    
    #BUG: TODO: is extending general_purpose_registers but not the weights a bug?
    general_purpose_registers+=general_working_registers

    
    branching_instructions=[ 'jmp','jmpr','jmp0','jmpl','jmprl','jmpr0',
                            'call','callr','call0','callr0','calll','callrl']

    #only set by result of instructions
    special_info_registers=['CRY','SGN','LOG','PLAYER']
    special_info_weights=[1,1,1,1]
    
    #only set by internal board_info
    stn_registers=['STN']
    stn_weights=[50]
    
    
    
    all_registers=(special_info_registers+
                   general_purpose_registers+
                   stn_registers
                   )
    
    modulated_registers={'WXY':9,
                         'X'  :9,#magic 9's agaion. board_Size..
                         'Y'  :9
                         }
    
    for working_reg in working_X_registers+working_Y_registers:
        modulated_registers[working_reg]=9
    
    #note, all_registers does not include *all* the registers.
    #it only includes the registers that are available to program space
    #(which is generally what people really mean when they say all_registers)
    

    player_reg_lookup={'black':-1,'white':1}
    
    def __init__(self,memoryons=640*1024): #ought to be enough for anyone
        self.max_memoryons=memoryons
        self.version="1.0"
    
    #Run the genome, with the board info (should metadata the board stuff out as is Go sepcific)
    def get_move(self,board=dict(),player=None,program=list()):
        self.boot(board=board,program=program)
        
        self.reg_PLAYER=GoVM.player_reg_lookup[player]
        log("exec starts:")
        log(datetime.datetime.now())
        pc_history=self.execute_program(max_clocks=4000) #up max clocks to twice. (5->10 hundred) what effect on current pop?
        log(datetime.datetime.now())
        log("exec ends:")
        
        
        move=(self.reg_X % 9,self.reg_Y % 9)
        self.set_board_info_memory() #TODO: FAST!
        return move,pc_history
    
    def initialise_memories(self):
        self.initialise_registers()
        self.initialise_memory()

    def initialise_registers(self):
        #internal control
        self.reg_pc=0   #pc and clock in lowercase for now, 
                        #as they are internal control registers
                        #not program space accessible. should extract/design out.

        self.PC_INTERRUPT=False
        self.PC_INTERRUPT_A=0
        self.SPECIAL_VAL_INTERRUPT=False
        self.SPECIAL_VAL_INTERRUPT_A=False
        self.reg_clock=0    #see self.reg_pc
        self.reg_HALT=False
        #

        self.reg_X=0    #
        self.reg_Y=0    # X and Y are also known as the move_registers
        self.reg_RES=0
        self.reg_CRY=0
        self.reg_SGN=0
        self.reg_LOG=1
        self.reg_STN=(0,0)
        self.reg_WXY=0
        
        [ setattr(self,'reg_'+N,0) for N in GoVM.general_purpose_registers ]
        [ setattr(self,'reg_'+N,0) for N in GoVM.working_X_registers ]
        [ setattr(self,'reg_'+N,0) for N in GoVM.working_Y_registers ]
        

    def initialise_memory(self):
        self.set_board_info_memory()
        self.memory=[0]*self.max_memoryons #1 memoryon is space for 1 value
        self.stack_memory=list()
        

    def set_board_info_memory(self):
        (self.bi_blacks,
         self.bi_whites,
         self.bi_spaces,
         self.bi_white_freedoms,
         self.bi_black_freedoms,
         self.bi_legal_moves, #not implemented
         self.bi_illegal_moves, #      "
         self.bi_all_stones)=board_info.get_board_info(board=self.board)

    def boot(self,board=dict(),program=list()):
        self.board=board
        self.program=program
        self.initialise_memories()
            
    def canonicalise(self,opcode,opdata):
        
        #Ok lets look at whats going on here.
        
        #opdata - a list of data opcodes.
        #opcodes can be,
        '''
            [digits]    -    constant value. use as is
            [REG]        -    use value currently in [REG]
            m[digits]    -    use value in memory at [digits]
            m[REG]       -    use value in memory at [REG]
            *[digits]    -    use value in memory at [digits] as m[digits]
            *[REG]        -    use value in memory at [REG] as m[digits]
            
        '''

        #this is the not flexible hacky way to do it.
        #hardcoded state machines. TODO: abstract and use metadata instead...
        new_opdata=list()
        for idx,opdatum in [ (idx,opdatum) for idx,opdatum in enumerate(opdata) if opdatum!= None ]:
            #are we dealing with REG or digits,?
            first=str(opdatum)[0]
            
            if first in '0123456789-':
                val=int(opdatum)
            elif first in 'm*':
                mem_loc=opdatum[1:]
                if mem_loc[0] in '0123456789-':
                    mem_loc=int(mem_loc)
                else:                                               #its a register
                    mem_loc=getattr(self,'reg_'+mem_loc)
                val=self.memory[mem_loc % self.max_memoryons]
                                                                    #print '\tm* deref->mem_loc',mem_loc,'val',val
                if first=='*':
                    val=self.memory[val % self.max_memoryons]            
                                                                    #print '\t\t*->',val
            else:                                                   #its a register
                                                                    #special case, if i'm the second opdatum and opcode is mov,
                                                                    #keep register name, dont canonicalise / rather, is already
                                                                    #standard representation for that data
                if (idx==1) and (opcode=='mov'):
                    val=opdatum
                elif opdatum[0:3]=='STN':
                    tokens=opdatum.split('_')
                    _op,boardpointer,stn_op=tokens
                    val=self.process_STN_op(bp=boardpointer,op=stn_op)
                    if val==None: val=0
                else:
                    val=getattr(self,'reg_'+opdatum)            
                                                                    #opdata[idx]=val #this turned out to be a really bad idea
            new_opdata.append(val)
        return new_opdata

    def process_STN_op(self,bp=None,op=None):
        if self.reg_STN==None:
            return
        if op=='STATS':
            return self.stn_STATS(bp)
        else:
            return self.stn_COORDS(op,bp)
        
    def stn_STATS(self,bp):
        coords=self.reg_STN
        x,y=coords
        offset=self.board_pointer_offsets[bp]
        xo,yo=offset
        x+=xo
        y+=yo
        coords=(x,y)
        state=0
        in_bi_black_freedoms=coords in self.bi_black_freedoms
        in_bi_white_freedoms=coords in self.bi_white_freedoms
        in_both_freedoms=in_bi_black_freedoms and in_bi_white_freedoms
        
        
        #order important
        if coords in self.bi_blacks:
            state=-1
        elif coords in self.bi_whites:
            state=1
        elif in_both_freedoms:
            state=4
        elif in_bi_black_freedoms:
            state=2
        elif in_bi_white_freedoms:
            state=3
        elif coords in self.bi_spaces:
            state=0
        else:
            #new coords off board
            state=9999
            #print 'COULD NOT DETERMINE STATE'
            #print coords
            #print self.bi_blacks
            #print self.bi_whites
            #print self.bi_spaces
            #sys.exit(0)
        return state
    
    def stn_COORDS(self,op,bp):
        xo,yo=self.board_pointer_offsets[bp]
        xs,ys=self.reg_STN
        xc=xs+xo
        yc=ys+yo
        if 'X' in op:
            return xc
        else:
            return yc            
            
            
        #TODO: add STN register. STN is the current stone under consideration,
        # from all_stones board memory info, current pointed to stone is
        # accessible with STN.   STN enables special info to be available with the following registers
        #        STN_{board_pointer}  select stone or neighbor to provide following info:
        #                           _STAT - STAT returns -1 /0 / 1 / 2 / 3 / 4 black, empty, white / black freedom / white freedom / both freedom
        #                                            into RES
        #                            _COORD - puts coordinate into selected working X/Y registers
        # 
        # set_stn instruction, sets coords used for stn sstn
        # next_stn                                        nstn
        # rev_stn                                        rstn
        #   NOTE: Stone is a bit of a misnomer, named because
        # it loops through all_stones list - but it maylso 
        #point to an empty space as indicated by set_stn
                
        ###board info instructions
        # these set STN based on the equivalent board_info lists
        # next_black
        # rev_black
        # next_white
        # rev_white
        # next_friendly
        # rev_friendly
        # next_enemy
        # rev_enemy
        
        # next_space
        # rev_space
        
        # next_white_freedom
        # rev_white_freedom
        # next_friendly_freedom
        # rev_friendly_freedom
        # next_enemy_freedom
        # rev_enemy_freedom
        # next_black_freedom
        # rev_black_freedom

    def ab(self,opdata):
        return opdata[0],opdata[1]

    def opcode_sstn(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_STN=(A,B)
        
    def opcode_nstn(self,opdata):
        self.reg_STN=self.bi_all_stones.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)

    def opcode_rstn(self,opdata):
        self.bi_all_stones.reverse()
    
    def opcode_nblk(self,opdata):
        self.reg_STN=self.bi_blacks.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rblk(self,opdata):
        self.bi_blacks.reverse()

    def opcode_nwht(self,opdata):
        self.reg_STN=self.bi_whites.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rwht(self,opdata):
        self.bi_whites.reverse()

    def opcode_nfrn(self,opdata):
        if self.reg_PLAYER==-1:
            self.reg_STN=self.bi_blacks.next()        
        else:
            self.reg_STN=self.bi_whites.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rfrn(self,opdata):
        if self.reg_PLAYER==-1:
            self.bi_blacks.reverse()        
        else:
            self.bi_whites.reverse()
            
    def opcode_nnme(self,opdata):
        if self.reg_PLAYER==-1:
            self.reg_STN=self.bi_whites.next()        
        else:
            self.reg_STN=self.bi_blacks.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rnme(self,opdata):
        if self.reg_PLAYER==-1:
            self.bi_whites.reverse()        
        else:
            self.bi_blacks.reverse()
            
    def opcode_nspc(self,opdata):
        self.reg_STN=self.bi_spaces.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rspc(self,opdata):
        self.bi_spaces.reverse()

    def opcode_nblkf(self,opdata):
        self.reg_STN=self.bi_black_freedoms.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rblkf(self,opdata):
        self.bi_black_freedoms.reverse()

    def opcode_nwhtf(self,opdata):
        self.reg_STN=self.bi_white_freedoms.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rwhtf(self,opdata):
        self.bi_white_freedoms.reverse()

    def opcode_nfrnf(self,opdata):
        if self.reg_PLAYER==-1:
            self.reg_STN=self.bi_black_freedoms.next()        
        else:
            self.reg_STN=self.bi_white_freedoms.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rfrnf(self,opdata):
        if self.reg_PLAYER==-1:
            self.bi_black_freedoms.reverse()        
        else:
            self.bi_white_freedoms.reverse()
            
    def opcode_nnmef(self,opdata):
        if self.reg_PLAYER==-1:
            self.reg_STN=self.bi_white_freedoms.next()        
        else:
            self.reg_STN=self.bi_black_freedoms.next()
        if self.reg_STN==0:
            self.reg_STN=(0,0)
        
    def opcode_rnmef(self,opdata):
        if self.reg_PLAYER==-1:
            self.bi_white_freedoms.reverse()        
        else:
            self.bi_black_freedoms.reverse()
    
    def opcode_iwxy(self,opdata):
        self.reg_WXY+=1
        if self.reg_WXY>7: self.reg_WXY=0

    def opcode_dwxy(self,opdata):
        self.reg_WXY-=1
        if self.reg_WXY<0: self.reg_WXY=7
    
    def opcode_add(self,opdata):
        #print '\tEXEC: opcode_add'
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A+B
        self.set_SGN()
        
    def opcode_sub(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A-B
        self.set_SGN()
    
    def opcode_incr(self,opdata): #Taking no data / accept empty or nothing passed, or None?
        #turns out, every opcode gets a list of 2 data items, and only inspects what they need. extra cruft is cruft! so sue me!
        self.opcode_add((self.reg_RES,1))
    
    def opcode_decr(self,opdata):
        self.opcode_sub((self.reg_RES,1))
        
    def opcode_mul(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A*B
        self.set_SGN()
        
    def opcode_div(self,opdata):
        A=opdata[0]
        B=opdata[1]
        try:
            self.reg_RES=A/B
            self.reg_CRY=A%B
        except ZeroDivisionError:
            self.reg_RES=0
            self.reg_CRY=0
        self.set_SGN()
        
            ######apply to board info registers, rot the circ.lists???
        ###  ERROR: Think about python and integers ...
###    def opcode_shiftl(self,opdata):
###        #shift left no carry/circle
###        A=opdata[0]                         ##Should ops that dont change carry leave it alone or clear it? -- clear it? (useful affect, as opposed to having to remember it to use it)
###        self.RES=A<<1
###        self.set_SGN()
###
###    def opcode_shiftr(self,opdata):
###        #shift right no carry/circle
###        A=opdata[0]                         ##Should ops that dont change carry leave it alone or clear it? -- clear it? (useful affect, as opposed to having to remember it to use it)
###        self.RES=A>>1
###        self.set_SGN()
###        
###    def opcode_shiftlc(self,opdata):
###        #shift left circular (why not, eh, why not?)
###        #preserve left bit and circle it round
###        #((binary word is length of current value))
###        A=opdata[0]
###        binary=bin(A)
###        print 'DEBUG: shiftlc binary=',binary
###        newbinary='0b'+''.join(binary[3:]+binary[2])
###        print 'DEBUG: shiftlc newbinary=',newbinary
###        self.reg_RES=int(newbinary,2)
###        self.set_SGN()
###        
###    def opcode_shiftrc(self,opdata):
###        #preserve left bit and circle it round
###        A=opdata[0]
###        binary=bin(A)
###        print 'DEBUG: shiftrc binary=',binary
###        newbinary='0b'+''.join(binary[-1]+binary[2:-1])
###        print 'DEBUG: shiftrc newbinary=',newbinary
###        self.reg_RES=int(newbinary,2)
###        self.set_SGN()
###    
###    def opcode_shiftly(self,opdata):
###        #shift left set CRY
###        A=opdata[0]
###        binary=bin(A)
###        CRY=binary[2]
###        newbinary='0b'+''.join(binary[3:])+'0'
###        self.reg_RES=int(newbinary,2)
###        self.reg_CRY=CRY
###        self.set_SGN()
###        
###    def opcode_shiftry(self,opdata):
###        #shift left set CRY
###        A=opdata[0]
###        binary=bin(A)
###        CRY=binary[2]
###        newbinary='0b0'+''.join(binary[2:-1])
###        self.reg_RES=int(newbinary,2)
###        self.reg_CRY=CRY
###        self.set_SGN()
            
    def opcode_cmpe(self,opdata):
        A=opdata[0]
        B=opdata[1]
        if A==B:
            self.reg_LOG=1
        else:
            self.reg_LOG=0
            
    def opcode_cmpne(self,opdata):
        A=opdata[0]
        B=opdata[1]
        if A!=B:
            self.reg_LOG=1
        else:
            self.reg_LOG=0
    
    def opcode_cmp0(self,opdata):
        A=opdata[0]
        if A==0:
            self.reg_LOG=1
        else:
            self.reg_LOG=0
    
    def opcode_cmplt(self,opdata):
        A=opdata[0]
        B=opdata[1]
        if A<B:
            self.reg_LOG=1
        else:
            self.reg_LOG=0

    def opcode_cmpgt(self,opdata):
        A=opdata[0]
        B=opdata[1]
        if A>B:
            self.reg_LOG=1
        else:
            self.reg_LOG=0

            
    def opcode_and(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A&B
        self.set_SGN()
        
    def opcode_or(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A|B
        self.set_SGN()
        
    def opcode_not(self,opdata):
        A=opdata[0]
        self.reg_RES=~A
        self.set_SGN()

    def opcode_xor(self,opdata):
        A=opdata[0]
        B=opdata[1]
        self.reg_RES=A^B#is that really xor?
        self.set_SGN()
        

    def opcode_jmp(self,opdata): #jmp, not call. so dont push/pop reg_pc + jmp onto the stack
        A=opdata[0]
        if A>0:
            self.PC_INTERRUPT=True
            self.PC_INTERRUPT_A=A
        
        

    def opcode_jmpr(self,opdata):
        A=opdata[0]
        if A!=0:
            abs_A=self.reg_pc+A
            #maybe have a jump relative to given address as well as current PC?
            self.opcode_jmp((abs_A,))

    def opcode_jmp0(self,opdata):
        A=opdata[0]
        if self.reg_RES==0:
            self.opcode_jmp((A,))
            
    def opcode_jmpl(self,opdata):
        A=opdata[0]
        if self.reg_LOG:
            self.opcode_jmp((A,))

    def opcode_jmprl(self,opdata):
        A=opdata[0]
        if A!=0:
            abs_A=self.reg_pc+A
            if self.reg_LOG:
                self.opcode_jmp((abs_A,))

            
    def opcode_jmpr0(self,opdata):
        A=opdata[0]
        if A!=0:
            if self.reg_RES==0:
                abs_A=self.reg_pc+A
                self.opcode_jmpr((abs_A,))
        
    def opcode_call(self,opdata):
        A=opdata[0]
        if A>0:
            self.push_pc()
            self.opcode_jmp((A,))
        
    def opcode_callr(self,opdata):
        A=opdata[0]
        if A!=0:
            self.push_pc()
            self.opcode_jmpr((A,))


    def opcode_call0(self,opdata):
        A=opdata[0]
        if A!=0:
            if self.reg_RES==0:
                self.push_pc()
                self.opcode_jmp((A,))

    def opcode_callr0(self,opdata):
        A=opdata[0]
        if A!=0:
            if self.reg_RES==0:
                self.push_pc()
                self.opcode_jmpr((A,))

    def opcode_calll(self,opdata):
        A=opdata[0]
        if A!=0:
            if self.reg_LOG:
                self.push_pc()
                self.opcode_jmp((A,))

    def opcode_callrl(self,opdata):
        A=opdata[0]
        if A!=0:
            if self.reg_LOG:
                self.push_pc()
                self.opcode_jmpr((A,))


    def opcode_ret(self,opdata):
        A=self.pop_pc()
        if A!=None:
            #print '\t\t..>returning'
            self.opcode_jmp((A,))

    def opcode_ret0(self,opdata):
        if self.reg_RES==0:
            A=self.pop_pc()
            if A!=None:
                #print '\t\t..>returning'
                self.opcode_jmp((A,))
    
    def opcode_retl(self,opdata):
        if self.reg_LOG:
            A=self.pop_pc()
            if A!=None:
                #print '\t\t..>returning'
                self.opcode_jmp((A,))

    def opcode_mov(self,opdata):
        A=opdata[0]
        if A==None: A=0
        B=opdata[1]
        if str(B)[0] not in '0123456789-':
            if B=='WXY': A=A % 9  ##Also all in modded registers
            setattr(self,'reg_'+B,A)
        else:
            self.memory[B % self.max_memoryons]=A
        self.set_SGN
            
    def opcode_push(self,opdata):
        A=opdata[0]
        self.push(A)
        
    def opcode_pop(self,opdata):
        A=self.pop()
        if A==None: A=0
        self.reg_RES=A

    def opcode_rnd(self):
        self.reg_RES=int(random.random()*config.rand_max)-(config.rand_max/2)
        self.set_SGN()
        
    
    def set_SGN(self):
        if self.reg_RES<0:
            self.reg_SGN=-1
        elif self.reg_RES==0:
            self.reg_SGN=0
        else:
            self.reg_SGN=1
    
    def push_pc(self):
        self.push(self.reg_pc+1) #MEMORY_OUT_OF_BOUNDS STARTS HERE.
        #((+1 to jump back to the intruction _after_ the originating call))
        
    def push(self,value):
        self.stack_memory.append(value)
        
    def pop(self):#**use the collections module, waz
        #return 0 if stack empty
        if len(self.stack_memory)==0: return None
        A=self.stack_memory[-1]
        self.stack_memory=self.stack_memory[:-1]
        return A
    
    def pop_pc(self):
        return self.pop()


    def execute_program(self,max_clocks=10000):
        #Go!
        #print 'execute_program called'
        
        pc_history=list()
        running_genome=open(config.vm_running_genome_file,'w')
        running_genome.write(repr(self.program.dna)+'\n')
        running_genome.close()
        #NEED TO IMPLEMENT pc LOOP DETECTION /ora t least stuck-pc etc../
        while (self.reg_clock<max_clocks) and (self.reg_pc<len(self.program)):
            if self.reg_pc<0:
                print 'DEBUG: REG_PC less than ZERO!! =',self.reg_pc
                print 'STAACK',self.stack_memory[-1:]
                global logging
                logging=True
                self.reg_pc=self.old_pc
                self.reg_HALT=True
            
            
            
            pc_history.append(self.reg_pc)
            op=self.program[self.reg_pc] #op = (opcode,[opdata1|None,opdata2|None])
                
            opcode=op[0]
            opdata=op[1]
            log('>CLOCK %d PC %d' %( self.reg_clock,self.reg_pc))
            log('\tBase op:'+opcode+str(opdata))
            opdata=self.canonicalise(opcode,opdata)
            log('\tCanonical: '+opcode+str(opdata))
            
            #exec
            self.opcodes[opcode](self,opdata)

            log('\top: '+opcode+str(opdata)+', pc %d, clk %d, RES %d, CRY %d, SGN %d, LOG %d, X:Y %d:%d' % (self.reg_pc,
                                                                                                            self.reg_clock,
                                                                                                            self.reg_RES,
                                                                                                            self.reg_CRY,
                                                                                                            self.reg_SGN,
                                                                                                            self.reg_LOG,
                                                                                                            self.reg_X,
                                                                                                            self.reg_Y))
            log('\tGP: %d %d %d %d %d %d %d %d' % (self.reg_GP0,
                            self.reg_GP1,
                            self.reg_GP2,
                            self.reg_GP3,
                            self.reg_GP4,
                            self.reg_GP5,
                            self.reg_GP6,
                            self.reg_GP7,
                            )
                )
            log('\tGX: %d %d %d %d %d %d %d %d' % (self.reg_X0,
                            self.reg_X1,
                            self.reg_X2,
                            self.reg_X3,
                            self.reg_X4,
                            self.reg_X5,
                            self.reg_X6,
                            self.reg_X7,
                            )
                )
            log('\tGY: %d %d %d %d %d %d %d %d' % (self.reg_Y0,
                            self.reg_Y1,
                            self.reg_Y2,
                            self.reg_Y3,
                            self.reg_Y4,
                            self.reg_Y5,
                            self.reg_Y6,
                            self.reg_Y7,
                            )
                )
            log('\tWXY %d PLAYER %d Stone %s' % (self.reg_WXY, self.reg_PLAYER, str(self.reg_STN)))
            
            log('\twhites'+str(self.bi_whites))
            log('\tblacks'+str(self.bi_blacks))
            log('\tspaces'+str(self.bi_spaces._direction))
            log('\twhiteF'+str(self.bi_white_freedoms))
            log('\tblackF'+str(self.bi_black_freedoms))
            log('\tallstns'+str(self.bi_all_stones))
            
            
            log('\tstack: ...'+str(len(self.stack_memory))+str(self.stack_memory[-10:]))
            log('\tMEM50: '+str(self.memory[0:50]))
            self.old_pc=self.reg_pc
            if self.PC_INTERRUPT:
                self.old_pc=self.reg_pc
                log('\tPC_INTERRUPT  ->  '+str(self.PC_INTERRUPT_A))
                self.reg_pc=self.PC_INTERRUPT_A % len(self.program)
                self.PC_INTERRUPT=False
                self.PC_INTERRUPT_A=None
            else:
                
                log('\tIncr reg_pc')
                self.reg_pc+=1
            if self.reg_HALT:
                print 'FORCED HALT BY reg_HALT'
                sys.exit(0)
            log('\tIncr reg_clock')
            self.reg_clock+=1
        return pc_history  
       # print 'HALT',self.reg_clock
        
        
        
    opcodes={'add':opcode_add,
          'sub':opcode_sub,
          'incr':opcode_incr,
          'decr':opcode_decr,
          'mul':opcode_mul,
          'div':opcode_div,
          'cmpe':opcode_cmpe,
          'cmpne':opcode_cmpne,
          'cmp0':opcode_cmp0,
          'cmplt':opcode_cmplt,
          'cmpgt':opcode_cmpgt,
          'and':opcode_and,
          'or':opcode_or,
          'not':opcode_not,
          'xor':opcode_xor,
          'jmp':opcode_jmp,
          'jmpr':opcode_jmpr,
          'jmp0':opcode_jmp0,
          'jmpl':opcode_jmpl,
          'jmprl':opcode_jmprl,
          'jmpr0':opcode_jmpr0,
          'call':opcode_call,
          'callr':opcode_callr,
          'call0':opcode_call0,
          'callr0':opcode_callr0,
          'calll':opcode_calll,
          'callrl':opcode_callrl,
          'ret':opcode_ret,
          'ret0':opcode_ret0,
          'retl':opcode_retl,
          'mov':opcode_mov,
          'push':opcode_push,
          'pop':opcode_pop,
          'rnd':opcode_rnd,
          #The ~special sauce~ from here down
          'sstn':opcode_sstn,
          'nstn':opcode_nstn,
          'rstn':opcode_rstn,
          'nblk':opcode_nblk,
          'nwht':opcode_nwht,
          'rwht':opcode_rwht,
          'nfrn':opcode_nfrn,
          'rfrn':opcode_rfrn,
          'nnme':opcode_nnme,
          'rnme':opcode_rnme,
          'nspc':opcode_nspc,
          'rspc':opcode_rspc,
          'nblkf':opcode_nblkf,
          'rblkf':opcode_rblkf,
          'nwhtf':opcode_nwhtf,
          'rwhtf':opcode_rwhtf,
          'nfrnf':opcode_nfrnf,
          'rfrnf':opcode_rfrnf,
          'nnmef':opcode_nnmef,
          'rnmef':opcode_rnmef,
          'iwxy':opcode_iwxy,
          'dwxy':opcode_dwxy,
                  }
