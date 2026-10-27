"""Interactive 3D network of proposed customer identity links.

Only purchase orders are used for volume exposure. Spatial position represents
country, identity type and recent PO volume; the edges distinguish *candidates*
from approved links. This is exploratory visualization, not a match authority.
"""
from html import escape
import math

import plotly.graph_objects as go

from database import load_df
from insights import DISPLAY_START

COUNTRY_ORDER = ("SG", "MY", "ID", "TH", "VN")
PALETTE = {
    "candidate": "#f59e73",
    "approved": "#2dd4bf",
    "canonical": "#76aaf4",
    "highlight": "#e9cb74",
}
SCENE_BG = "#111f35"


def _positions(cases):
    points = []
    for cc in COUNTRY_ORDER:
        part = cases[cases["country"] == cc].sort_values("alias_id")
        for i, row in enumerate(part.itertuples(index=False)):
            x = COUNTRY_ORDER.index(cc) * 6 + i * 0.88
            points.append((row, x))
    return points


def build_identity_network(cases, highlighted_alias=None):
    """Plotly figure with interactive orbit, zoom, tooltips and status legend."""
    volume=load_df(
        """SELECT customer_id,SUM(qty) AS po_units FROM transactions
           WHERE record_type='PO' AND period>=?
           GROUP BY customer_id""",
        (DISPLAY_START,),
    )
    units=dict(zip(volume.customer_id,volume.po_units))
    rows=_positions(cases)
    fig=go.Figure()
    lines={"candidate":( [], [], [] ), "approved":( [], [], [] )}
    nodes={
        "candidate":([], [], [], [], [], []),
        "approved":([], [], [], [], [], []),
        "canonical":([], [], [], [], [], []),
    }
    for case,x in rows:
        approved=case.status=="Resolved"
        edge_type="approved" if approved else "candidate"
        alias_units=int(case.alias_12m_units)
        canonical_units=int(units.get(case.target_id,0))
        alias_height=max(1,alias_units)
        canonical_height=max(1,canonical_units)
        for index,v in enumerate([x,x,None]):
            lines[edge_type][0].append(v)
            lines[edge_type][1].append([0,1,None][index])
            lines[edge_type][2].append([alias_height,canonical_height,None][index])

        tip_base=("<b>"+escape(str(case.alias_name))+"</b> · "+escape(str(case.alias_id))+
                  "<br>Potential retained record: "+escape(str(case.target_id))+
                  "<br>Market: "+escape(str(case.country))+
                  "<br>Status: "+escape(str(case.status))+
                  "<br>Review priority: "+escape(str(case.priority))+
                  "<br>Alias PO volume: "+format(alias_units,",")+" units in 12 months"+
                  "<br>Candidate linkage requires human approval")
        emphasized=case.alias_id==highlighted_alias
        v=nodes[edge_type]
        v[0].append(x);v[1].append(0);v[2].append(alias_height)
        v[3].append(tip_base)
        v[4].append(13 if emphasized else min(11,5+2.2*math.log1p(alias_units)/3))
        v[5].append(PALETTE["highlight"] if emphasized else PALETTE[edge_type])
        target=nodes["canonical"]
        target[0].append(x);target[1].append(1);target[2].append(canonical_height)
        target[3].append("<b>"+escape(str(case.target_name))+"</b> · "+
                         escape(str(case.target_id))+
                         "<br>Market: "+escape(str(case.country))+
                         "<br>12-month retained-ID PO units: "+format(canonical_units,","))
        target[4].append(8 if emphasized else 6)
        target[5].append(PALETTE["highlight"] if emphasized else PALETTE["canonical"])

    for kind,label in (("candidate","Proposed link"),("approved","Approved link")):
        x,y,z=lines[kind]
        fig.add_trace(go.Scatter3d(
            x=x,y=y,z=z,mode="lines",name=label,hoverinfo="skip",
            line=dict(color=PALETTE[kind],width=5 if kind=="approved" else 3),
            showlegend=True,
        ))
    for kind,label in (("candidate","Candidate identity"),("approved","Approved alias"),
                       ("canonical","Golden-record candidate")):
        x,y,z,tips,sizes,colors=nodes[kind]
        if not x: continue
        fig.add_trace(go.Scatter3d(
            x=x,y=y,z=z,mode="markers",name=label,
            marker=dict(size=sizes,color=colors,opacity=.94,
                        line=dict(color="#dbe8f4",width=.45)),
            hovertext=tips,hovertemplate="%{hovertext}<extra></extra>",
            showlegend=True,
        ))
    centers=[i*6+1.8 for i in range(len(COUNTRY_ORDER))]
    fig.update_layout(
        paper_bgcolor=SCENE_BG,
        font=dict(family="Arial, sans-serif",color="#e6eff9",size=12),
        margin=dict(l=3,r=3,t=14,b=3),
        height=460,
        legend=dict(orientation="h",y=-.03,x=0,
                    bgcolor="rgba(0,0,0,0)",font=dict(size=11)),
        scene=dict(
            bgcolor=SCENE_BG,
            xaxis=dict(title="Market",tickvals=centers,ticktext=list(COUNTRY_ORDER),
                       color="#b5c6d9",showbackground=False,showspikes=False,
                       gridcolor="#314660"),
            yaxis=dict(title="Identity type",tickvals=[0,1],
                       ticktext=["Alias","Golden"],color="#b5c6d9",
                       gridcolor="#314660",showbackground=False,showspikes=False),
            zaxis=dict(title="Confirmed PO units / 12m",
                       color="#b5c6d9",gridcolor="#314660",
                       showbackground=False,showspikes=False),
            camera=dict(eye=dict(x=1.7,y=-1.85,z=1.2)),
            aspectmode="manual",aspectratio=dict(x=2.2,y=.8,z=1),
        ),
    )
    return fig
