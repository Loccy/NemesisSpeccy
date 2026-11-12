import pickle, sys
for n in sys.argv[1:]:
    try: d=pickle.load(open('nxf8/%s.raw.pkl'%n,'rb'))
    except Exception as e: print(n, e); continue
    fr=d['frames']; s8=[r for r in fr if r[2]==8 and r[1]==5]
    out=[]
    for i in range(0,len(s8)-50,250):
        a,b=s8[i],s8[i+50]; out.append((a[3], b[6]-a[6]))
    st=d['stage_start']; secs=(st[(2,1)][0]-st[(1,8)][0])/50 if (2,1) in st else None
    print(n, 'stage 8 seconds', secs, out[16:31])
