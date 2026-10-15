import ast,os,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
SOURCE=Path(__file__).resolve().parents[1]/'pacman/pacman.pyw'

def load():
 tree=ast.parse(SOURCE.read_text(encoding='utf-8'));nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in {'fruit','fruit_disabled','game'}]
 ns={'os':os,'thisGame':SimpleNamespace(fruitTimer=100,mode=1),'snd_fruitbounce':SimpleNamespace(play=lambda:None)}
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SOURCE),'exec'),ns)
 f=ns['fruit'].__new__(ns['fruit']);f.__dict__.update(slowTimer=0,x=16,y=16,velX=1,velY=0,speed=1,active=True,bouncei=0,bounceY=0,nearestRow=1,nearestCol=1,currentPath=False)
 return f,ns

class FruitRegressionTests(unittest.TestCase):
 def test_fruit_disabled_by_default_with_explicit_enable_override(self):
  with patch.dict(os.environ):
   os.environ.pop('PACMAN_DISABLE_FRUIT',None)
   f,ns=load();self.assertTrue(ns['fruit_disabled']())
   f.currentPath='RR';f.Move();self.assertFalse(f.active);self.assertIs(f.Draw(),False)
   os.environ['PACMAN_DISABLE_FRUIT']='0'
   self.assertFalse(ns['fruit_disabled']())
 def test_no_route_cancels_before_grid_and_clears_stale_velocity(self):
  with patch.dict(os.environ,{'PACMAN_DISABLE_FRUIT':'0'}):
   for x in [16,17,31]:
    f,ns=load();f.x=x;f.Move();self.assertFalse(f.active);self.assertEqual((f.x,f.velX,f.velY,f.currentPath),(x,0,0,''));self.assertEqual(ns['thisGame'].fruitTimer,0)
 def test_follow_no_route_cancels_spawn(self):
  f,ns=load();f.FollowNextPathWay();self.assertFalse(f.active);self.assertEqual(f.currentPath,'');self.assertEqual(ns['thisGame'].fruitTimer,0)
 def test_valid_path_reaches_next_tile_and_consumes_one_direction(self):
  with patch.dict(os.environ,{'PACMAN_DISABLE_FRUIT':'0'}):
   f,_=load();f.currentPath='RR'
   for _ in range(32):f.Move()
   self.assertEqual((f.x,f.y,f.currentPath,f.velX,f.velY),(32,16,'R',1,0));self.assertTrue(f.active)
 def test_disabled_fruit_neither_moves_nor_draws(self):
  with patch.dict(os.environ,{'PACMAN_DISABLE_FRUIT':'1'}):
   f,ns=load();f.currentPath='RR';f.Move();self.assertIs(f.Draw(),False);self.assertFalse(f.active);self.assertEqual((f.x,f.y,f.velX,f.velY),(16,16,0,0))
 def test_disabled_hud_hides_icon_but_explicit_enable_keeps_it(self):
  for disabled in ['0','1']:
   with self.subTest(disabled=disabled),patch.dict(os.environ,{'PACMAN_DISABLE_FRUIT':disabled}):
    _,ns=load();draw=[];ns['screen']=SimpleNamespace(blit=lambda *args:draw.append(args));ns['thisFruit']=SimpleNamespace(imFruit={0:object()},fruitType=0)
    g=ns['game'].__new__(ns['game']);g.score=0;g.levelNum=1;g.lives=0;g.mode=1;g.screenSize=(112,112);g.DrawNumber=lambda *args:None;g.IsCurriculumOne=lambda:False;g.DrawScore();self.assertEqual(len(draw),0 if disabled=='1' else 1)

if __name__=='__main__':unittest.main()
