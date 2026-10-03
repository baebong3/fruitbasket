import json,random,sys
from pathlib import Path
random.seed(int(sys.argv[2]))
fr=[("411","사과","05","후지","04","상품","10개"),("411","사과","06","홍로","04","상품","10개"),("412","배","01","신고","04","상품","10개"),("414","감귤","01","노지","04","상품","10개"),("415","단감","00","단감","04","상품","10개"),("418","바나나","02","수입","04","상품","100g"),("413","복숭아","01","백도","04","상품","10개"),("421","포도","07","샤인머스켓","04","상품","2kg"),("421","포도","02","캠벨얼리","04","상품","1kg"),("424","키위","01","뉴질랜드","04","상품","10개")]
vg=[("211","배추","01","봄","04","상품","1포기"),("214","무","01","월동","04","상품","1개"),("246","양파","00","양파","04","상품","1kg"),("232","대파","00","대파","04","상품","1kg"),("231","오이","02","다다기","04","상품","10개")]
base={n+k:random.randint(2000,60000) for _,n,_,k,*_ in fr+vg}
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
lab=["당일 (10/02)","1일전 (10/01)","1주일전 (09/25)","2주일전","1개월전","1년전","일평년"]
for cls in ("01","02"):
  for cat,rows in (("400",fr),("200",vg)):
    items=[]
    for ic,n,kc,k,rc,r,u in rows:
      b=base[n+k]*(0.6 if cls=="02" else 1)
      vals=[b*random.uniform(.7,1.5) for _ in lab]
      d={"item_name":n,"item_code":ic,"kind_name":k,"kind_code":kc,"rank":r,"rank_code":rc,"unit":u}
      for i,(l,v) in enumerate(zip(lab,vals),1):
        d[f"day{i}"]=l; d[f"dpr{i}"]=f"{int(v):,}"
      if n=="키위": d["dpr7"]="-"
      items.append(d)
    (out/f"{cls}_{cat}.json").write_text(json.dumps({"condition":[],"data":{"error_code":"000","item":items}},ensure_ascii=False))
