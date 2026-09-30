(() => {
  'use strict';

  const $ = id => document.getElementById(id);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const COMPONENT = {
    5120: {size:1, get:'getInt8'}, 5121: {size:1, get:'getUint8'},
    5122: {size:2, get:'getInt16'}, 5123: {size:2, get:'getUint16'},
    5125: {size:4, get:'getUint32'}, 5126: {size:4, get:'getFloat32'}
  };
  const TYPE_N = {SCALAR:1, VEC2:2, VEC3:3, VEC4:4, MAT2:4, MAT3:9, MAT4:16};

  function parseGLB(buffer){
    const dv = new DataView(buffer);
    if (dv.getUint32(0, true) !== 0x46546c67) throw new Error('File không phải GLB hợp lệ');
    if (dv.getUint32(4, true) !== 2) throw new Error('Viewer chỉ hỗ trợ GLB/glTF 2.0');
    let offset = 12, json = null, bin = null;
    while (offset + 8 <= buffer.byteLength){
      const len = dv.getUint32(offset, true), type = dv.getUint32(offset + 4, true);
      const start = offset + 8, end = start + len;
      if (end > buffer.byteLength) throw new Error('GLB bị thiếu dữ liệu');
      if (type === 0x4E4F534A){
        json = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, start, len)).replace(/\0+$/,''));
      } else if (type === 0x004E4942){
        bin = buffer.slice(start, end);
      }
      offset = end;
    }
    if (!json || !bin) throw new Error('GLB thiếu JSON/BIN chunk');
    return {json, bin};
  }

  function normalizedValue(value, componentType){
    if (componentType === 5120) return Math.max(value / 127, -1);
    if (componentType === 5121) return value / 255;
    if (componentType === 5122) return Math.max(value / 32767, -1);
    if (componentType === 5123) return value / 65535;
    return value;
  }

  function readAccessor(doc, bin, index, forceFloat=false){
    const acc = doc.accessors[index];
    if (!acc || acc.bufferView == null) throw new Error('Accessor GLB không được hỗ trợ');
    const view = doc.bufferViews[acc.bufferView];
    if (!view) throw new Error('bufferView GLB không hợp lệ');
    const comp = COMPONENT[acc.componentType], n = TYPE_N[acc.type];
    if (!comp || !n) throw new Error('Kiểu accessor GLB chưa hỗ trợ');
    const stride = view.byteStride || comp.size * n;
    const base = (view.byteOffset || 0) + (acc.byteOffset || 0);
    const data = new DataView(bin);
    const count = acc.count * n;
    const isIndex = acc.type === 'SCALAR' && !forceFloat;
    const out = isIndex ? new Uint32Array(count) : new Float32Array(count);
    for (let i=0;i<acc.count;i++){
      const row = base + i * stride;
      for (let j=0;j<n;j++){
        let value = data[comp.get](row + j*comp.size, true);
        if (acc.normalized) value = normalizedValue(value, acc.componentType);
        out[i*n+j] = value;
      }
    }
    return {data:out, size:n, count:acc.count};
  }

  function computeNormals(positions, indices){
    const out = new Float32Array(positions.length);
    const triCount = Math.floor(indices.length/3);
    for (let t=0;t<triCount;t++){
      const ia=indices[t*3]*3, ib=indices[t*3+1]*3, ic=indices[t*3+2]*3;
      const ax=positions[ia], ay=positions[ia+1], az=positions[ia+2];
      const bx=positions[ib], by=positions[ib+1], bz=positions[ib+2];
      const cx=positions[ic], cy=positions[ic+1], cz=positions[ic+2];
      const abx=bx-ax, aby=by-ay, abz=bz-az, acx=cx-ax, acy=cy-ay, acz=cz-az;
      const nx=aby*acz-abz*acy, ny=abz*acx-abx*acz, nz=abx*acy-aby*acx;
      for (const i of [ia,ib,ic]){out[i]+=nx;out[i+1]+=ny;out[i+2]+=nz;}
    }
    for (let i=0;i<out.length;i+=3){
      const l=Math.hypot(out[i],out[i+1],out[i+2]) || 1;
      out[i]/=l;out[i+1]/=l;out[i+2]/=l;
    }
    return out;
  }

  function makeSequential(count){ const a = new Uint32Array(count); for(let i=0;i<count;i++) a[i]=i; return a; }

  function wireIndices(indices){
    const out = new Uint32Array(Math.floor(indices.length/3)*6);
    let o=0;
    for(let i=0;i+2<indices.length;i+=3){
      const a=indices[i],b=indices[i+1],c=indices[i+2];
      out[o++]=a;out[o++]=b; out[o++]=b;out[o++]=c; out[o++]=c;out[o++]=a;
    }
    return out;
  }

  function baseMaterial(doc, prim){
    const mat = doc.materials?.[prim.material] || {};
    const pbr = mat?.pbrMetallicRoughness || {};
    const factor = pbr.baseColorFactor || [0.72,0.78,0.88,1];
    return {
      color: [Number(factor[0]??.72), Number(factor[1]??.78), Number(factor[2]??.88), Number(factor[3]??1)],
      textureIndex: pbr.baseColorTexture?.index ?? null,
      doubleSided: !!mat.doubleSided,
      alphaMode: mat.alphaMode || 'OPAQUE',
    };
  }

  function boundsOf(prims){
    let min=[Infinity,Infinity,Infinity], max=[-Infinity,-Infinity,-Infinity];
    for(const p of prims){
      const a=p.positions;
      for(let i=0;i<a.length;i+=3){
        min[0]=Math.min(min[0],a[i]); min[1]=Math.min(min[1],a[i+1]); min[2]=Math.min(min[2],a[i+2]);
        max[0]=Math.max(max[0],a[i]); max[1]=Math.max(max[1],a[i+1]); max[2]=Math.max(max[2],a[i+2]);
      }
    }
    // Degenerate geometry (empty/zero-size/NaN positions) must never produce
    // a black/broken frame - fall back to a unit cube around the origin so
    // downstream centering/scaling always has finite numbers to work with.
    const finite = min.every(Number.isFinite) && max.every(Number.isFinite);
    if (!finite) { min=[-0.5,-0.5,-0.5]; max=[0.5,0.5,0.5]; }
    return {min,max,size:[max[0]-min[0],max[1]-min[1],max[2]-min[2]]};
  }

  function rotateZ(prims, angle){
    const c=Math.cos(angle), s=Math.sin(angle);
    for(const p of prims){
      for(let i=0;i<p.positions.length;i+=3){
        const x=p.positions[i], y=p.positions[i+1];
        p.positions[i]=c*x-s*y; p.positions[i+1]=s*x+c*y;
      }
      if (p.normals){
        for(let i=0;i<p.normals.length;i+=3){
          const x=p.normals[i], y=p.normals[i+1];
          p.normals[i]=c*x-s*y; p.normals[i+1]=s*x+c*y;
        }
      }
    }
  }

  function rotateX(prims, angle){
    const c=Math.cos(angle), s=Math.sin(angle);
    for(const p of prims){
      for(let i=0;i<p.positions.length;i+=3){
        const y=p.positions[i+1], z=p.positions[i+2];
        p.positions[i+1]=c*y-s*z; p.positions[i+2]=s*y+c*z;
      }
      if (p.normals){
        for(let i=0;i<p.normals.length;i+=3){
          const y=p.normals[i+1], z=p.normals[i+2];
          p.normals[i+1]=c*y-s*z; p.normals[i+2]=s*y+c*z;
        }
      }
    }
  }

  function autoUpright(prims){
    const {size} = boundsOf(prims);
    let mode = 'native';
    if (size[0] > size[1] * 1.3 && size[0] > size[2] * 1.1){
      rotateZ(prims, -Math.PI / 2);
      mode = 'auto-z-90';
    } else if (size[2] > size[1] * 1.3 && size[2] > size[0] * 1.1){
      rotateX(prims, -Math.PI / 2);
      mode = 'auto-x-90';
    }
    return mode;
  }

  function fitPrimitives(prims){
    const {min,max} = boundsOf(prims);
    const c=[(min[0]+max[0])/2,(min[1]+max[1])/2,(min[2]+max[2])/2];
    const radius=Math.max(max[0]-min[0],max[1]-min[1],max[2]-min[2])/2 || 1;
    const scale=1/radius;
    for(const p of prims){
      for(let i=0;i<p.positions.length;i+=3){
        p.positions[i]=(p.positions[i]-c[0])*scale;
        p.positions[i+1]=(p.positions[i+1]-c[1])*scale;
        p.positions[i+2]=(p.positions[i+2]-c[2])*scale;
      }
    }
  }

  function shader(gl, type, source){
    const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);
    if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)||'Shader compile lỗi');
    return s;
  }
  function program(gl, vs, fs){
    const p=gl.createProgram(); gl.attachShader(p,shader(gl,gl.VERTEX_SHADER,vs));gl.attachShader(p,shader(gl,gl.FRAGMENT_SHADER,fs));gl.linkProgram(p);
    if(!gl.getProgramParameter(p,gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p)||'Shader link lỗi');
    return p;
  }
  function perspective(fov, aspect, near, far){
    const f=1/Math.tan(fov/2), nf=1/(near-far);
    return new Float32Array([f/aspect,0,0,0, 0,f,0,0, 0,0,(far+near)*nf,-1, 0,0,(2*far*near)*nf,0]);
  }

  async function decodeImageBitmap(blob){
    if (window.createImageBitmap) return await createImageBitmap(blob);
    return await new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = err => { URL.revokeObjectURL(url); reject(err); };
      img.src = url;
    });
  }

  function imageBlobFromSource(doc, bin, sourceIndex){
    const source = doc.images?.[sourceIndex];
    if (!source) return null;
    if (source.bufferView == null) return null;
    const view = doc.bufferViews?.[source.bufferView];
    if (!view) return null;
    const begin = view.byteOffset || 0;
    const end = begin + view.byteLength;
    const bytes = new Uint8Array(bin.slice(begin, end));
    return new Blob([bytes], {type: source.mimeType || 'image/png'});
  }

  async function loadTextureBitmap(doc, bin, textureIndex, cache){
    if (textureIndex == null) return null;
    if (cache.has(textureIndex)) return await cache.get(textureIndex);
    const texDef = doc.textures?.[textureIndex];
    const promise = (async () => {
      const blob = imageBlobFromSource(doc, bin, texDef?.source);
      if (!blob) return null;
      return await decodeImageBitmap(blob);
    })();
    cache.set(textureIndex, promise);
    return await promise;
  }

  async function extractPrimitives(doc, bin){
    const textureCache = new Map();
    const meshNode = new Map();
    (doc.nodes || []).forEach((node, nodeIndex) => {
      if (node?.mesh != null && !meshNode.has(node.mesh)) meshNode.set(node.mesh, {nodeIndex, skinIndex: node.skin ?? null});
    });
    const out=[];
    for (let meshIndex=0; meshIndex<(doc.meshes || []).length; meshIndex++){
      const mesh=doc.meshes[meshIndex];
      const nodeInfo=meshNode.get(meshIndex) || {nodeIndex:null, skinIndex:null};
      for (const prim of (mesh.primitives || [])){
        if (prim.mode != null && prim.mode !== 4) continue;
        if (prim.attributes?.POSITION == null) continue;
        const p = readAccessor(doc, bin, prim.attributes.POSITION, true).data;
        const idx = prim.indices != null ? readAccessor(doc, bin, prim.indices, false).data : makeSequential(p.length/3);
        const n = prim.attributes.NORMAL != null ? readAccessor(doc, bin, prim.attributes.NORMAL, true).data : computeNormals(p, idx);
        const uv = prim.attributes?.TEXCOORD_0 != null ? readAccessor(doc, bin, prim.attributes.TEXCOORD_0, true).data : null;
        const joints = prim.attributes?.JOINTS_0 != null ? readAccessor(doc, bin, prim.attributes.JOINTS_0, true).data : null;
        const weights = prim.attributes?.WEIGHTS_0 != null ? readAccessor(doc, bin, prim.attributes.WEIGHTS_0, true).data : null;
        const material = baseMaterial(doc, prim);
        const textureBitmap = material.textureIndex != null ? await loadTextureBitmap(doc, bin, material.textureIndex, textureCache) : null;
        out.push({
          positions:p, normals:n, indices:idx, uvs:uv,
          joints, weights, skinIndex:nodeInfo.skinIndex, nodeIndex:nodeInfo.nodeIndex,
          color:material.color, textureBitmap, hasTexture:!!(textureBitmap && uv),
          doubleSided:material.doubleSided, alphaMode:material.alphaMode,
        });
      }
    }
    if (!out.length) throw new Error('Không tìm thấy mesh tam giác trong GLB');
    return out;
  }

  function mat4Identity(){return new Float32Array([1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]);}
  function mat4Mul(a,b){
    const o=new Float32Array(16);
    for(let c=0;c<4;c++) for(let r=0;r<4;r++) o[c*4+r]=a[0*4+r]*b[c*4+0]+a[1*4+r]*b[c*4+1]+a[2*4+r]*b[c*4+2]+a[3*4+r]*b[c*4+3];
    return o;
  }
  function mat4Inverse(a){
    const o=new Float32Array(16);
    const a00=a[0],a01=a[1],a02=a[2],a03=a[3],a10=a[4],a11=a[5],a12=a[6],a13=a[7],a20=a[8],a21=a[9],a22=a[10],a23=a[11],a30=a[12],a31=a[13],a32=a[14],a33=a[15];
    const b00=a00*a11-a01*a10,b01=a00*a12-a02*a10,b02=a00*a13-a03*a10,b03=a01*a12-a02*a11,b04=a01*a13-a03*a11,b05=a02*a13-a03*a12,b06=a20*a31-a21*a30,b07=a20*a32-a22*a30,b08=a20*a33-a23*a30,b09=a21*a32-a22*a31,b10=a21*a33-a23*a31,b11=a22*a33-a23*a32;
    let det=b00*b11-b01*b10+b02*b09+b03*b08-b04*b07+b05*b06; if(!det)return mat4Identity(); det=1/det;
    o[0]=(a11*b11-a12*b10+a13*b09)*det;o[1]=(-a01*b11+a02*b10-a03*b09)*det;o[2]=(a31*b05-a32*b04+a33*b03)*det;o[3]=(-a21*b05+a22*b04-a23*b03)*det;
    o[4]=(-a10*b11+a12*b08-a13*b07)*det;o[5]=(a00*b11-a02*b08+a03*b07)*det;o[6]=(-a30*b05+a32*b02-a33*b01)*det;o[7]=(a20*b05-a22*b02+a23*b01)*det;
    o[8]=(a10*b10-a11*b08+a13*b06)*det;o[9]=(-a00*b10+a01*b08-a03*b06)*det;o[10]=(a30*b04-a31*b02+a33*b00)*det;o[11]=(-a20*b04+a21*b02-a23*b00)*det;
    o[12]=(-a10*b09+a11*b07-a12*b06)*det;o[13]=(a00*b09-a01*b07+a02*b06)*det;o[14]=(-a30*b03+a31*b01-a32*b00)*det;o[15]=(a20*b03-a21*b01+a22*b00)*det;
    return o;
  }
  function quatNorm(q){const l=Math.hypot(q[0],q[1],q[2],q[3])||1;return [q[0]/l,q[1]/l,q[2]/l,q[3]/l];}
  function quatSlerp(a,b,t){
    let [ax,ay,az,aw]=quatNorm(a),[bx,by,bz,bw]=quatNorm(b); let cos=ax*bx+ay*by+az*bz+aw*bw;
    if(cos<0){cos=-cos;bx=-bx;by=-by;bz=-bz;bw=-bw;}
    if(cos>.9995)return quatNorm([ax+t*(bx-ax),ay+t*(by-ay),az+t*(bz-az),aw+t*(bw-aw)]);
    const th=Math.acos(clamp(cos,-1,1)),s=Math.sin(th),a0=Math.sin((1-t)*th)/s,b0=Math.sin(t*th)/s;
    return [ax*a0+bx*b0,ay*a0+by*b0,az*a0+bz*b0,aw*a0+bw*b0];
  }
  function mat4FromTRS(t=[0,0,0],q=[0,0,0,1],s=[1,1,1]){
    const [x,y,z,w]=quatNorm(q),x2=x+x,y2=y+y,z2=z+z,xx=x*x2,xy=x*y2,xz=x*z2,yy=y*y2,yz=y*z2,zz=z*z2,wx=w*x2,wy=w*y2,wz=w*z2;
    return new Float32Array([(1-(yy+zz))*s[0],(xy+wz)*s[0],(xz-wy)*s[0],0,(xy-wz)*s[1],(1-(xx+zz))*s[1],(yz+wx)*s[1],0,(xz+wy)*s[2],(yz-wx)*s[2],(1-(xx+yy))*s[2],0,t[0],t[1],t[2],1]);
  }
  function nodeBaseTRS(node){return {t:[...(node.translation||[0,0,0])],q:[...(node.rotation||[0,0,0,1])],s:[...(node.scale||[1,1,1])]};}
  function buildParents(doc){const p=new Array((doc.nodes||[]).length).fill(-1);(doc.nodes||[]).forEach((n,i)=>(n.children||[]).forEach(c=>p[c]=i));return p;}
  function accessorAsArray(doc,bin,index){return readAccessor(doc,bin,index,true).data;}
  function animationRuntime(doc,bin){
    const parents=buildParents(doc),base=(doc.nodes||[]).map(nodeBaseTRS);
    const skins=(doc.skins||[]).map(skin=>{
      const ibmData=skin.inverseBindMatrices!=null?accessorAsArray(doc,bin,skin.inverseBindMatrices):null;
      const ibm=[];for(let i=0;i<skin.joints.length;i++)ibm.push(ibmData?new Float32Array(ibmData.slice(i*16,i*16+16)):mat4Identity());
      return {joints:[...skin.joints],ibm};
    });
    const clips=(doc.animations||[]).map((anim,animIndex)=>{
      let duration=0;const channels=[];
      for(const ch of (anim.channels||[])){
        const sp=anim.samplers?.[ch.sampler];if(!sp||ch.target?.node==null)continue;
        const times=accessorAsArray(doc,bin,sp.input),values=accessorAsArray(doc,bin,sp.output);if(times.length)duration=Math.max(duration,times[times.length-1]);
        channels.push({node:ch.target.node,path:ch.target.path,times,values,interp:sp.interpolation||'LINEAR'});
      }
      return {name:anim.name||`clip_${animIndex+1}`,duration:Math.max(duration,0.001),channels};
    });
    return {parents,base,skins,clips};
  }
  function sampleChannel(ch,time){
    const times=ch.times;if(!times.length)return null;if(time<=times[0])return valueAt(ch,0);const last=times.length-1;if(time>=times[last])return valueAt(ch,last);
    let hi=1;while(hi<times.length&&times[hi]<time)hi++;const lo=hi-1,dt=(times[hi]-times[lo])||1,u=clamp((time-times[lo])/dt,0,1),a=valueAt(ch,lo),b=valueAt(ch,hi);
    if(ch.path==='rotation')return quatSlerp(a,b,u);return a.map((v,i)=>v+(b[i]-v)*u);
  }
  function valueAt(ch,i){const n=ch.path==='rotation'?4:3,o=i*n;return Array.from(ch.values.slice(o,o+n));}
  function globalsFor(runtime,clip,time,doc){
    const trs=runtime.base.map(v=>({t:[...v.t],q:[...v.q],s:[...v.s]}));
    if(clip)for(const ch of clip.channels){const v=sampleChannel(ch,time);if(!v)continue;const dst=trs[ch.node];if(!dst)continue;if(ch.path==='translation')dst.t=v;else if(ch.path==='rotation')dst.q=v;else if(ch.path==='scale')dst.s=v;}
    const local=trs.map((v,i)=>doc.nodes?.[i]?.matrix?new Float32Array(doc.nodes[i].matrix):mat4FromTRS(v.t,v.q,v.s)),global=new Array(local.length);
    const calc=i=>{if(global[i])return global[i];const p=runtime.parents[i];return global[i]=p>=0?mat4Mul(calc(p),local[i]):local[i];};for(let i=0;i<local.length;i++)calc(i);return global;
  }

  class LocalGLBViewer{
    constructor(root, canvas){
      this.root=root;this.canvas=canvas;this.gl=canvas.getContext('webgl2',{antialias:true,alpha:true});
      if(!this.gl) throw new Error('Trình duyệt không hỗ trợ WebGL2');
      this.meshes=[];this.yaw=-0.45;this.pitch=-0.18;this.roll=0;this.distance=3.3;this.pan=[0,0];
      this.wire=false;this.auto=false;this.showTexture=true;this.drag=null;this.last=[0,0];this.url='';this.meta={};this.captureSize=null;
      this.animRuntime=null;this.animDoc=null;this.animClip=null;this.animPlaying=false;this.animStart=0;this.animTime=0;this.animLoop=true;this.animDone=false;this._onAnimationDone=null;
      this._initGL();this._events();this._frame=this._frame.bind(this);requestAnimationFrame(this._frame);
    }
    _initGL(){
      const gl=this.gl;
      const vs=`#version 300 es\nprecision highp float;
in vec3 aPosition;in vec3 aNormal;in vec2 aUV;in vec4 aJoints;in vec4 aWeights;
uniform mat4 uProj;uniform float uYaw,uPitch,uRoll,uDistance;uniform vec2 uPan;
uniform bool uSkinned;uniform mat4 uBones[64];uniform vec3 uCenter;uniform float uScale;
out vec3 vNormal;out vec3 vPos;out vec2 vUV;
vec3 rotX(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(p.x,c*p.y-s*p.z,s*p.y+c*p.z);}
vec3 rotY(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(c*p.x+s*p.z,p.y,-s*p.x+c*p.z);}
vec3 rotZ(vec3 p,float a){float c=cos(a),s=sin(a);return vec3(c*p.x-s*p.y,s*p.x+c*p.y,p.z);}
void main(){
  vec3 p=aPosition;vec3 n=aNormal;
  if(uSkinned){
    mat4 skin=aWeights.x*uBones[int(aJoints.x+0.5)]+aWeights.y*uBones[int(aJoints.y+0.5)]+aWeights.z*uBones[int(aJoints.z+0.5)]+aWeights.w*uBones[int(aJoints.w+0.5)];
    p=(skin*vec4(p,1.0)).xyz;n=mat3(skin)*n;
  }
  p=(p-uCenter)*uScale;n=normalize(n);
  p=rotZ(rotY(rotX(p,uPitch),uYaw),uRoll);n=normalize(rotZ(rotY(rotX(n,uPitch),uYaw),uRoll));p.xy+=uPan;p.z-=uDistance;vNormal=n;vPos=p;vUV=aUV;gl_Position=uProj*vec4(p,1.0);
}`;
      const fs=`#version 300 es\nprecision highp float;in vec3 vNormal;in vec3 vPos;in vec2 vUV;uniform vec4 uColor;uniform bool uUseTexture;uniform sampler2D uTex;out vec4 outColor;void main(){vec4 texel=uUseTexture?texture(uTex,vUV):vec4(1.0);vec4 base=vec4(uColor.rgb*texel.rgb,uColor.a*texel.a);vec3 n=normalize(vNormal);vec3 L=normalize(vec3(-0.45,0.75,0.85));float d=max(dot(n,L),0.0);float rim=pow(1.0-max(dot(n,normalize(-vPos)),0.0),2.2)*0.18;vec3 col=base.rgb*(0.28+0.72*d)+rim*vec3(0.45,0.68,1.0);outColor=vec4(col,base.a);}`;
      this.prog=program(gl,vs,fs);gl.useProgram(this.prog);
      this.loc={pos:gl.getAttribLocation(this.prog,'aPosition'),norm:gl.getAttribLocation(this.prog,'aNormal'),uv:gl.getAttribLocation(this.prog,'aUV'),joints:gl.getAttribLocation(this.prog,'aJoints'),weights:gl.getAttribLocation(this.prog,'aWeights'),proj:gl.getUniformLocation(this.prog,'uProj'),yaw:gl.getUniformLocation(this.prog,'uYaw'),pitch:gl.getUniformLocation(this.prog,'uPitch'),roll:gl.getUniformLocation(this.prog,'uRoll'),dist:gl.getUniformLocation(this.prog,'uDistance'),pan:gl.getUniformLocation(this.prog,'uPan'),color:gl.getUniformLocation(this.prog,'uColor'),useTex:gl.getUniformLocation(this.prog,'uUseTexture'),tex:gl.getUniformLocation(this.prog,'uTex'),skinned:gl.getUniformLocation(this.prog,'uSkinned'),bones:gl.getUniformLocation(this.prog,'uBones[0]'),center:gl.getUniformLocation(this.prog,'uCenter'),scale:gl.getUniformLocation(this.prog,'uScale')};
      gl.enable(gl.DEPTH_TEST); gl.enable(gl.CULL_FACE); gl.cullFace(gl.BACK); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.uniform1i(this.loc.tex,0);
    }
    _events(){
      this.canvas.addEventListener('contextmenu',e=>e.preventDefault());
      this.canvas.addEventListener('pointerdown',e=>{this.canvas.setPointerCapture(e.pointerId);this.drag=e.button===2?'pan':'orbit';this.last=[e.clientX,e.clientY];});
      this.canvas.addEventListener('pointermove',e=>{if(!this.drag)return;const dx=e.clientX-this.last[0],dy=e.clientY-this.last[1];this.last=[e.clientX,e.clientY];if(this.drag==='orbit'){this.yaw+=dx*.008;this.pitch=clamp(this.pitch+dy*.008,-1.48,1.48);}else{const k=.003*this.distance;this.pan[0]+=dx*k;this.pan[1]-=dy*k;}});
      const stop=e=>{this.drag=null;try{this.canvas.releasePointerCapture(e.pointerId)}catch(_){}};
      this.canvas.addEventListener('pointerup',stop);this.canvas.addEventListener('pointercancel',stop);
      this.canvas.addEventListener('wheel',e=>{e.preventDefault();this.distance=clamp(this.distance*Math.exp(e.deltaY*.0012),1.55,9);},{passive:false});
      this.root.addEventListener('dblclick',()=>this.reset());
    }
    reset(){this.yaw=-0.45;this.pitch=-0.18;this.roll=0;this.distance=3.3;this.pan=[0,0];}
    rotateXQuarter(dir){this.pitch+=dir*Math.PI/2;}
    rotateZQuarter(dir){this.roll+=dir*Math.PI/2;}
    setWire(on){this.wire=!!on;}
    setAuto(on){this.auto=!!on;}
    setTexture(on){this.showTexture=!!on;}
    async captureTurntable({duration=8, ratio='1:1', fps=30}={}){
      if(!this.meshes.length) throw new Error('Chưa có model 3D trong viewer');
      if(!this.canvas.captureStream || !window.MediaRecorder) throw new Error('Trình duyệt chưa hỗ trợ quay Viewer 3D');
      duration = Number(duration) >= 12 ? 12 : 8;
      const size = ratio === '16:9' ? [1920,1080] : [1080,1080];
      const old={auto:this.auto,yaw:this.yaw,pitch:this.pitch,roll:this.roll,distance:this.distance,pan:[...this.pan],captureSize:this.captureSize};
      this.auto=false;this.captureSize=size;this.yaw=0;this.pitch=-0.12;this.roll=0;this.pan=[0,0];this.distance=3.25;
      await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
      const mimeCandidates=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'];
      const mime=mimeCandidates.find(x=>MediaRecorder.isTypeSupported?.(x)) || 'video/webm';
      const stream=this.canvas.captureStream(fps);
      const chunks=[];const rec=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:12_000_000});
      rec.ondataavailable=e=>{if(e.data?.size)chunks.push(e.data)};
      const stopped=new Promise((resolve,reject)=>{rec.onstop=resolve;rec.onerror=e=>reject(e.error||e)});
      rec.start(250);
      const start=performance.now(), total=duration*1000;
      await new Promise(resolve=>{
        const step=now=>{
          const t=Math.min(1,(now-start)/total);
          this.yaw=t*Math.PI*2;
          if(t<1) requestAnimationFrame(step); else resolve();
        };
        requestAnimationFrame(step);
      });
      await new Promise(r=>setTimeout(r,120));
      rec.stop();await stopped;stream.getTracks().forEach(t=>t.stop());
      this.auto=old.auto;this.yaw=old.yaw;this.pitch=old.pitch;this.roll=old.roll;this.distance=old.distance;this.pan=old.pan;this.captureSize=old.captureSize;
      return new Blob(chunks,{type:mime});
    }
    async load(url, opts={}){
      const type = opts.type || 'auto';
      this.url=url;this._clearMeshes();this.stopAnimation();
      const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error(`Không tải được GLB (${r.status})`);
      const {json,bin}=parseGLB(await r.arrayBuffer());
      const prims=await extractPrimitives(json,bin);
      const hasSkin=prims.some(p=>p.skinIndex!=null&&p.joints&&p.weights);
      // Auto-upright uses a single-bbox-aspect-ratio heuristic that assumes
      // "1 ambiguous-orientation object" (typical of a marching-cubes
      // character/prop). A map/large scene is already Y-up by construction
      // and can legitimately be very wide/flat, which would otherwise be
      // mis-detected as "sideways" and rotated wrong - skip it for maps.
      const allowUpright = type !== 'map';
      let uprightMode='native';
      if(hasSkin){
        const b=boundsOf(prims),c=[(b.min[0]+b.max[0])/2,(b.min[1]+b.max[1])/2,(b.min[2]+b.max[2])/2],radius=Math.max(b.max[0]-b.min[0],b.max[1]-b.min[1],b.max[2]-b.min[2])/2||1;
        for(const p of prims){p.normCenter=c;p.normScale=1/radius;}
        this.animRuntime=animationRuntime(json,bin);this.animDoc=json;
      }else{
        this.animRuntime=null;this.animDoc=null;if(allowUpright)uprightMode=autoUpright(prims);fitPrimitives(prims);for(const p of prims){p.normCenter=[0,0,0];p.normScale=1;}
      }
      this._upload(prims);this.reset();
      const textured=prims.filter(p=>p.hasTexture).length,animations=this.animRuntime?.clips?.map(c=>c.name)||[];
      this.meta={parts:prims.length,triangles:prims.reduce((sum,p)=>sum+Math.floor(p.indices.length/3),0),texturedParts:textured,uprightMode,skinned:hasSkin,animations,type};
      this.showTexture=textured>0;
      if(animations.length)this.playAnimation(animations.find(n=>n.toLowerCase()==='idle')||animations[0]);
      return this.meta;
    }
    playAnimation(name, {loop=true}={}){
      const clip=this.animRuntime?.clips?.find(c=>c.name===name)||this.animRuntime?.clips?.find(c=>c.name.toLowerCase()===String(name||'').toLowerCase());
      if(!clip)return false;
      this.animClip=clip;this.animPlaying=true;this.animLoop=loop;this.animDone=false;this.animStart=performance.now()-this.animTime*1000;
      return true;
    }
    stopAnimation(){this.animPlaying=false;this.animClip=null;this.animTime=0;this.animLoop=true;this.animDone=false;}
    getAnimations(){return this.animRuntime?.clips?.map(c=>c.name)||[];}
    getCurrentAnimation(){return this.animClip?.name||null;}
    _boneMatrices(mesh,now){
      if(!this.animRuntime||mesh.skinIndex==null)return null;
      const skin=this.animRuntime.skins?.[mesh.skinIndex];if(!skin||skin.joints.length>64)return null;
      let t=0;
      if(this.animClip){
        if(this.animPlaying){
          const elapsed=(now-this.animStart)/1000;
          if(this.animLoop){
            this.animTime=elapsed%this.animClip.duration;
          }else if(elapsed>=this.animClip.duration){
            this.animTime=this.animClip.duration;
            if(!this.animDone){this.animDone=true;this._onAnimationDone?.(this.animClip.name);}
          }else{
            this.animTime=elapsed;
          }
        }
        t=this.animTime;
      }
      const globals=globalsFor(this.animRuntime,this.animClip,t,this.animDoc),meshGlobal=mesh.nodeIndex!=null?globals[mesh.nodeIndex]:mat4Identity(),invMesh=mat4Inverse(meshGlobal),flat=new Float32Array(64*16);
      for(let i=0;i<64;i++)flat.set(mat4Identity(),i*16);
      skin.joints.forEach((joint,i)=>flat.set(mat4Mul(mat4Mul(invMesh,globals[joint]),skin.ibm[i]),i*16));
      return flat;
    }
    _clearMeshes(){
      const gl=this.gl;
      for(const m of this.meshes){
        for(const b of [m.pb,m.nb,m.ub,m.jb,m.wtb,m.ib,m.wb]) if(b) gl.deleteBuffer(b);
        if(m.tex) gl.deleteTexture(m.tex);
      }
      this.meshes=[];
    }
    _upload(prims){
      const gl=this.gl;
      for(const p of prims){
        const pb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,pb);gl.bufferData(gl.ARRAY_BUFFER,p.positions,gl.STATIC_DRAW);
        const nb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,nb);gl.bufferData(gl.ARRAY_BUFFER,p.normals,gl.STATIC_DRAW);
        const uvData = p.uvs || new Float32Array((p.positions.length/3)*2);
        const ub=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,ub);gl.bufferData(gl.ARRAY_BUFFER,uvData,gl.STATIC_DRAW);
        let jb=null,wtb=null;
        if(p.joints&&p.weights){jb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,jb);gl.bufferData(gl.ARRAY_BUFFER,p.joints,gl.STATIC_DRAW);wtb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,wtb);gl.bufferData(gl.ARRAY_BUFFER,p.weights,gl.STATIC_DRAW);}
        const ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,p.indices,gl.STATIC_DRAW);
        const wi=wireIndices(p.indices),wb=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,wb);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,wi,gl.STATIC_DRAW);
        let tex=null;
        if (p.hasTexture){
          tex=gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, tex);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
          gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
          gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, p.textureBitmap);
          gl.generateMipmap(gl.TEXTURE_2D);
          if (p.textureBitmap.close) try{ p.textureBitmap.close(); }catch(_){ }
        }
        this.meshes.push({pb,nb,ub,jb,wtb,ib,wb,count:p.indices.length,wcount:wi.length,color:p.color,tex,hasTexture:p.hasTexture,doubleSided:p.doubleSided,alphaMode:p.alphaMode,skinIndex:p.skinIndex,nodeIndex:p.nodeIndex,normCenter:p.normCenter||[0,0,0],normScale:p.normScale||1,skinned:!!(jb&&wtb&&p.skinIndex!=null)});
      }
    }
    _resize(){const dpr=Math.min(devicePixelRatio||1,2),w=this.captureSize?this.captureSize[0]:Math.max(2,Math.floor(this.canvas.clientWidth*dpr)),h=this.captureSize?this.captureSize[1]:Math.max(2,Math.floor(this.canvas.clientHeight*dpr));if(this.canvas.width!==w||this.canvas.height!==h){this.canvas.width=w;this.canvas.height=h;}this.gl.viewport(0,0,w,h);return w/h;}
    _frame(now=performance.now()){
      if(this.auto && !document.hidden) this.yaw+=0.004;
      const gl=this.gl,aspect=this._resize();gl.clearColor(0.129,0.110,0.098,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(this.prog);
      gl.uniformMatrix4fv(this.loc.proj,false,perspective(Math.PI/4,aspect,.05,50));gl.uniform1f(this.loc.yaw,this.yaw);gl.uniform1f(this.loc.pitch,this.pitch);gl.uniform1f(this.loc.roll,this.roll);gl.uniform1f(this.loc.dist,this.distance);gl.uniform2f(this.loc.pan,this.pan[0],this.pan[1]);
      for(const m of this.meshes){
        if (m.doubleSided) gl.disable(gl.CULL_FACE); else gl.enable(gl.CULL_FACE);
        gl.bindBuffer(gl.ARRAY_BUFFER,m.pb);gl.enableVertexAttribArray(this.loc.pos);gl.vertexAttribPointer(this.loc.pos,3,gl.FLOAT,false,0,0);
        gl.bindBuffer(gl.ARRAY_BUFFER,m.nb);gl.enableVertexAttribArray(this.loc.norm);gl.vertexAttribPointer(this.loc.norm,3,gl.FLOAT,false,0,0);
        gl.bindBuffer(gl.ARRAY_BUFFER,m.ub);gl.enableVertexAttribArray(this.loc.uv);gl.vertexAttribPointer(this.loc.uv,2,gl.FLOAT,false,0,0);
        if(m.skinned){
          gl.bindBuffer(gl.ARRAY_BUFFER,m.jb);gl.enableVertexAttribArray(this.loc.joints);gl.vertexAttribPointer(this.loc.joints,4,gl.FLOAT,false,0,0);
          gl.bindBuffer(gl.ARRAY_BUFFER,m.wtb);gl.enableVertexAttribArray(this.loc.weights);gl.vertexAttribPointer(this.loc.weights,4,gl.FLOAT,false,0,0);
          gl.uniform1i(this.loc.skinned,1);const bones=this._boneMatrices(m,now);if(bones)gl.uniformMatrix4fv(this.loc.bones,false,bones);
        }else{
          gl.disableVertexAttribArray(this.loc.joints);gl.vertexAttrib4f(this.loc.joints,0,0,0,0);gl.disableVertexAttribArray(this.loc.weights);gl.vertexAttrib4f(this.loc.weights,1,0,0,0);gl.uniform1i(this.loc.skinned,0);
        }
        gl.uniform3fv(this.loc.center,m.normCenter);gl.uniform1f(this.loc.scale,m.normScale);
        gl.uniform4fv(this.loc.color,m.color);
        const useTex = !!(this.showTexture && m.hasTexture && m.tex);
        gl.uniform1i(this.loc.useTex,useTex ? 1 : 0);
        if (useTex){ gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,m.tex); }
        if(this.wire){gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,m.wb);gl.drawElements(gl.LINES,m.wcount,gl.UNSIGNED_INT,0);}else{gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,m.ib);gl.drawElements(gl.TRIANGLES,m.count,gl.UNSIGNED_INT,0);}
      }
      requestAnimationFrame(this._frame);
    }
  }

  let viewer=null,currentUrl='',meta={};
  function ensure(){if(!viewer)viewer=new LocalGLBViewer($('ai3dStageViewer'),$('ai3dCanvas'));return viewer;}
  function restoreStage(){
    $('ai3dStageViewer').classList.add('hidden');
    const S=window.Studio;
    if(S?.hasVideo()){ $('videoBox').classList.remove('hidden'); $('empty').classList.add('hidden'); }
    else { $('videoBox').classList.add('hidden'); $('empty').classList.remove('hidden'); }
    document.querySelector('.transport')?.classList.remove('viewer-transport-hidden');
  }
  function updateDebugPanel(){
    const el=$('ai3dViewerDebug'); if(!el) return;
    if(!meta || !meta.parts){ el.classList.add('hidden'); return; }
    el.classList.remove('hidden');
    const v=ensure();
    el.textContent =
      `Mesh: ${meta.parts} phần · ${(meta.triangles||0).toLocaleString('vi-VN')} tam giác  |  ` +
      `Skin: ${meta.skinned ? 'YES' : 'NO'}  |  ` +
      `Animations: ${(meta.animations||[]).join(', ') || '(không có)'}  |  ` +
      `Current: ${v.getCurrentAnimation() || '(dừng)'}`;
  }

  async function show(url, arg='Model 3D'){
    // Backward-compatible options: show(url, "Label text") - legacy string
    // form - or show(url, {label, type, autoFit, autoRotate}) - section 34
    // contract. type: "character" | "prop" | "map" (default: auto-detect
    // via skin presence, same heuristic as before).
    const opts = (typeof arg === 'string') ? {label: arg} : (arg || {});
    const label = opts.label || 'Model 3D';
    currentUrl=url;
    $('empty').classList.add('hidden');$('videoBox').classList.add('hidden');$('busy').classList.add('hidden');
    $('mapHdStageViewer')?.classList.add('hidden'); // avoid overlapping with Bản đồ HD's own stage view, if it was open
    $('realtimePreview')?.classList.add('hidden');
    $('ai3dStageViewer').classList.remove('hidden');document.querySelector('.transport')?.classList.add('viewer-transport-hidden');
    $('ai3dViewerState').textContent='Đang tải model 3D…';
    const hadModelBefore = ensure().meshes.length > 0;
    try{
      const v=ensure();
      v.setAuto(!!opts.autoRotate);
      meta=await v.load(url, {type: opts.type});
      const textureText = meta.texturedParts ? ` · texture màu ${meta.texturedParts}/${meta.parts} phần` : ' · chưa có texture, đang dùng shading';
      const uprightText = meta.uprightMode !== 'native' ? ' · auto dựng đứng' : '';
      const animText=meta.animations?.length?` · animation: ${meta.animations.join(' / ')}`:'';
      $('ai3dViewerState').textContent=`${label} · ${meta.parts} phần · ${meta.triangles.toLocaleString('vi-VN')} tam giác${textureText}${uprightText}${animText}`;
      const animIds=['ai3dViewerAnimIdle','ai3dViewerAnimRun','ai3dViewerAnimAttack','ai3dViewerAnimStop'];
      animIds.forEach(id=>$(id)?.classList.toggle('hidden',!(meta.animations?.length)));
      const btn = $('ai3dViewerMode');
      if (btn){
        btn.classList.toggle('active', v.showTexture);
        btn.textContent = v.showTexture ? '🎨 Texture ON' : '🎨 Texture OFF';
        btn.disabled = !meta.texturedParts;
      }
      updateDebugPanel();
    }
    catch(e){
      $('ai3dViewerState').textContent='Không thể hiển thị GLB: '+e.message;
      window.Studio?.setStatus('Viewer 3D lỗi: '+e.message,true);
      $('ai3dViewerDebug')?.classList.add('hidden');
      // Section 20: never leave a blank/broken canvas - if this viewer never
      // had a model loaded before, fall back to whatever the module's own
      // empty/source state is instead of showing a stuck black canvas.
      if(!hadModelBefore) restoreStage();
    }
  }

  function playNamedAnimation(preferred){
    const v=ensure(),names=v.getAnimations();if(!names.length)return;
    const wanted=names.find(n=>n.toLowerCase()===preferred)||names.find(n=>n.toLowerCase().includes(preferred))||names[0];
    const isOneShot = preferred.includes('attack');
    if(isOneShot){
      v._onAnimationDone = () => {
        const idleName = names.find(n=>n.toLowerCase()==='idle');
        if(idleName) v.playAnimation(idleName);
        updateDebugPanel();
      };
      if(v.playAnimation(wanted, {loop:false})){
        $('ai3dViewerState').textContent=`Animation đang phát: ${wanted} (1 lần) · ${meta.triangles?.toLocaleString('vi-VN')||0} tam giác`;
      }
    } else {
      v._onAnimationDone = null;
      if(v.playAnimation(wanted)) $('ai3dViewerState').textContent=`Animation đang phát: ${wanted} · ${meta.triangles?.toLocaleString('vi-VN')||0} tam giác`;
    }
    updateDebugPanel();
  }
  $('ai3dViewerAnimIdle')?.addEventListener('click',()=>playNamedAnimation('idle'));
  $('ai3dViewerAnimRun')?.addEventListener('click',()=>playNamedAnimation('run'));
  $('ai3dViewerAnimAttack')?.addEventListener('click',()=>playNamedAnimation('attack_01'));
  $('ai3dViewerAnimStop')?.addEventListener('click',()=>{ensure().stopAnimation();$('ai3dViewerState').textContent='Animation đã dừng';updateDebugPanel();});

  $('ai3dViewerReset')?.addEventListener('click',()=>ensure().reset());
  $('ai3dViewerWire')?.addEventListener('click',e=>{const on=e.currentTarget.classList.toggle('active');ensure().setWire(on);e.currentTarget.textContent=on?'▦ Wireframe ON':'▦ Wireframe';});
  $('ai3dViewerAuto')?.addEventListener('click',e=>{const on=e.currentTarget.classList.toggle('active');ensure().setAuto(on);e.currentTarget.textContent=on?'⟳ Tự xoay ON':'⟳ Tự xoay';});
  $('ai3dViewerMode')?.addEventListener('click',e=>{const on=!ensure().showTexture;ensure().setTexture(on);e.currentTarget.classList.toggle('active',on);e.currentTarget.textContent=on?'🎨 Texture ON':'🎨 Texture OFF';});

  $('ai3dViewerRotXm')?.addEventListener('click',()=>ensure().rotateXQuarter(-1));
  $('ai3dViewerRotXp')?.addEventListener('click',()=>ensure().rotateXQuarter(1));
  $('ai3dViewerRotZm')?.addEventListener('click',()=>ensure().rotateZQuarter(-1));
  $('ai3dViewerRotZp')?.addEventListener('click',()=>ensure().rotateZQuarter(1));
  $('ai3dViewerFull')?.addEventListener('click',async()=>{const el=$('ai3dStageViewer');try{if(!document.fullscreenElement)await el.requestFullscreen();else await document.exitFullscreen();}catch(_){}});
  $('ai3dOpenViewer')?.addEventListener('click',()=>{if(currentUrl)show(currentUrl,'Model 3D');});
  document.querySelectorAll('.tool').forEach(btn=>btn.addEventListener('click',()=>{if(btn.dataset.tool==='ai3d' && currentUrl) show(currentUrl,'Model 3D'); else if(btn.dataset.tool!=='ai3d') restoreStage();}));

  window.AIVF3DViewer={show,hide:restoreStage,get currentUrl(){return currentUrl;},get meta(){return meta;},captureTurntable:(opts)=>ensure().captureTurntable(opts)};
})();
