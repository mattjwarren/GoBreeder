import data_structures

def get_board_info(board=dict(),xmin=0,ymin=0,xmax=8,ymax=8):
    #states, B blacks, W whites, S spaces, BF Black Freedoms, WF White Freedoms,
    #LM legal moves, IM illegal moves
    #SM stupid moves //managed by mediator//
    #WM winning moves (moves that win) //managed by mediator//
    #BG - black groups
    #WG - White groups
    
    blacks=data_structures.CircularList()
    whites=data_structures.CircularList()
    spaces=data_structures.CircularList()
    white_freedoms=data_structures.CircularList()
    black_freedoms=data_structures.CircularList()

    for x in range(xmin,xmax+1):
        for y in range(ymin,ymax+1):
            if board[(x,y)]==-1:
                state_type=blacks
            elif board[(x,y)]==0:
                state_type=spaces
                
                local_blacks,local_whites,_local_spaces=get_surrounding_states(board=board,
                                                                              coords=(x,y),
                                                                              stoneset='straight')
                white_freedoms.add_value((x,y)) if local_whites else ()
                black_freedoms.add_value((x,y)) if local_blacks else ()
                
            elif board[(x,y)]==1:
                state_type=whites
                
            state_type.add_value((x,y))
    
    legal_moves=spaces
    illegal_moves=blacks+whites 
    all_stones=blacks+whites
    return (blacks,whites,spaces,
            white_freedoms,black_freedoms,
            legal_moves, illegal_moves,
            all_stones) #TODO: !!!!<><><><><><<><><< moves and all stones as opcodes


def get_surrounding_states(board=dict(),coords=tuple(),stoneset='all'):
    xc,yc=coords
    straight_coords=[(0,1),(-1,0),(1,0),(0,-1)]
    diagonal_coords=[(-1,-1),(1,1),(-1,-1),(1,-1)]
    all_coords=straight_coords+diagonal_coords
    if stoneset=='straight':
        get_list=straight_coords
    elif stoneset=='diagonal':
        get_list=diagonal_coords
    else:
        get_list=all_coords
    
    black_stones=[]
    white_stones=[]
    spaces=[]
    for x,y in get_list:
         
        x=x+xc
        y=y+yc
        if (not x<0) and (not x>8) and (not y<0) and (not y>8):
            if board[(x,y)]==-1:
                state_type=black_stones
            elif board[(x,y)]==0:
                state_type=spaces
            elif board[(x,y)]==1:
                state_type=white_stones
            state_type.append((x,y))
    return black_stones,white_stones,spaces