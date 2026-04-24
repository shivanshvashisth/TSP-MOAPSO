import schemdraw
from schemdraw.flow import *

# Create the drawing
with schemdraw.Drawing(file='PSO_Flowchart_Final.jpg', show=False) as d:
    d.config(fontsize=11)

    # 1. Start Node
    start = Start().label('Start')

    # 2. Initialization
    Arrow().down().length(d.unit / 2)
    init = Box(w=5.5, h=1.8).label(
        'Initialize position $X_i, V_i$. Set $pBest_i=X_i$.\nCalculate $gBest$. Set $g=0, w=0.9, c_1=c_2=2.0$')

    # 3. Adaptive Params
    Arrow().down().length(d.unit / 2)
    adaptive = Box(w=6.5, h=1.8).label(
        'Estimate the evolutionary states of the algorithm and\nadaptively control the parameters. Perform elitist\nlearning operation in convergence state')

    # 4. i = 1
    Arrow().down().length(d.unit / 2)
    i_init = Box(w=2.5, h=0.6).label('$i=1$')

    # 5. Check i <= N
    Arrow().down().length(d.unit / 2)
    check_n = Decision(w=3.5, h=2.5, E='yes', S='no').label('$i \leq N$')

    # 6. Update P/V (Inner Loop)
    Arrow().at(check_n.E).right().length(d.unit / 2)
    update = Box(w=4.5, h=1).label('Update the velocity and\nposition of particle $i$')

    # 7. Boundary Check
    Arrow().down().at(update.S).length(d.unit / 2)
    check_x = Decision(w=4.5, h=2.5, E='yes', S='no').label('$X_{min} \leq X_i \leq X_{max}$')

    # 8. Evaluate
    Arrow().at(check_x.E).right().length(d.unit / 2)
    eval_p = Box(w=3.5, h=1.2).label('Evaluate particle $i$\nUpdate $pBest_i$ and $gBest$')

    # 9. Increment i
    # Connect Eval and 'No' path from check_x to inc_i
    Line().down().at(eval_p.S).length(d.unit)
    line_bottom = Line().left().tox(check_n.S)
    Line().at(check_x.S).down().toy(line_bottom.end)

    Arrow().down().at(line_bottom.end).length(d.unit / 2)
    inc_i = Box(w=2.5, h=0.6).label('$i=i+1$')

    # 10. Loop back to i check
    Line().left().at(inc_i.W).length(d.unit)
    Line().up().toy(check_n.W)
    Arrow().right().tox(check_n.W)

    # 11. Exit i Loop (Increment g)
    # Positioning g+1 below the i loop
    Arrow().at(check_n.S).down().length(d.unit * 5)  # Length adjusted to clear i-loop boxes
    inc_g = Box(w=2.5, h=0.6).label('$g=g+1$')

    # 12. Check g < G
    Arrow().down().at(inc_g.S).length(d.unit / 2)
    check_g = Decision(w=3.5, h=2.5, E='yes', S='no').label('$g < G$')

    # 13. Loop back to Adaptive (Yes)
    Line().right().at(check_g.E).length(d.unit * 5)
    Line().up().toy(adaptive.E)
    Arrow().left().tox(adaptive.E)

    # 14. Finish (No)
    Arrow().down().at(check_g.S).length(d.unit / 2)
    Finish = Start().label('Finish')

print("High-quality flowchart saved as PSO_Flowchart_Final.jpg")