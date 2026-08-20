var St=globalThis,At=St.ShadowRoot&&(St.ShadyCSS===void 0||St.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,ro=Symbol(),So=new WeakMap,pt=class{constructor(e,i,o){if(this._$cssResult$=!0,o!==ro)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=i}get styleSheet(){let e=this.o,i=this.t;if(At&&e===void 0){let o=i!==void 0&&i.length===1;o&&(e=So.get(i)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),o&&So.set(i,e))}return e}toString(){return this.cssText}},x=t=>new pt(typeof t=="string"?t:t+"",void 0,ro),p=(t,...e)=>{let i=t.length===1?t[0]:e.reduce((o,r,a)=>o+(n=>{if(n._$cssResult$===!0)return n.cssText;if(typeof n=="number")return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+t[a+1],t[0]);return new pt(i,t,ro)},Ao=(t,e)=>{if(At)t.adoptedStyleSheets=e.map(i=>i instanceof CSSStyleSheet?i:i.styleSheet);else for(let i of e){let o=document.createElement("style"),r=St.litNonce;r!==void 0&&o.setAttribute("nonce",r),o.textContent=i.cssText,t.appendChild(o)}},oo=At?t=>t:t=>t instanceof CSSStyleSheet?(e=>{let i="";for(let o of e.cssRules)i+=o.cssText;return x(i)})(t):t;var{is:Ba,defineProperty:Ta,getOwnPropertyDescriptor:Ea,getOwnPropertyNames:za,getOwnPropertySymbols:Da,getPrototypeOf:Ia}=Object,Pt=globalThis,Po=Pt.trustedTypes,Ra=Po?Po.emptyScript:"",ja=Pt.reactiveElementPolyfillSupport,ht=(t,e)=>t,ut={toAttribute(t,e){switch(e){case Boolean:t=t?Ra:null;break;case Object:case Array:t=t==null?t:JSON.stringify(t)}return t},fromAttribute(t,e){let i=t;switch(e){case Boolean:i=t!==null;break;case Number:i=t===null?null:Number(t);break;case Object:case Array:try{i=JSON.parse(t)}catch{i=null}}return i}},Ot=(t,e)=>!Ba(t,e),Oo={attribute:!0,type:String,converter:ut,reflect:!1,useDefault:!1,hasChanged:Ot};Symbol.metadata??=Symbol("metadata"),Pt.litPropertyMetadata??=new WeakMap;var Ze=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,i=Oo){if(i.state&&(i.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((i=Object.create(i)).wrapped=!0),this.elementProperties.set(e,i),!i.noAccessor){let o=Symbol(),r=this.getPropertyDescriptor(e,o,i);r!==void 0&&Ta(this.prototype,e,r)}}static getPropertyDescriptor(e,i,o){let{get:r,set:a}=Ea(this.prototype,e)??{get(){return this[i]},set(n){this[i]=n}};return{get:r,set(n){let v=r?.call(this);a?.call(this,n),this.requestUpdate(e,v,o)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??Oo}static _$Ei(){if(this.hasOwnProperty(ht("elementProperties")))return;let e=Ia(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(ht("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(ht("properties"))){let i=this.properties,o=[...za(i),...Da(i)];for(let r of o)this.createProperty(r,i[r])}let e=this[Symbol.metadata];if(e!==null){let i=litPropertyMetadata.get(e);if(i!==void 0)for(let[o,r]of i)this.elementProperties.set(o,r)}this._$Eh=new Map;for(let[i,o]of this.elementProperties){let r=this._$Eu(i,o);r!==void 0&&this._$Eh.set(r,i)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let i=[];if(Array.isArray(e)){let o=new Set(e.flat(1/0).reverse());for(let r of o)i.unshift(oo(r))}else e!==void 0&&i.push(oo(e));return i}static _$Eu(e,i){let o=i.attribute;return o===!1?void 0:typeof o=="string"?o:typeof e=="string"?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,i=this.constructor.elementProperties;for(let o of i.keys())this.hasOwnProperty(o)&&(e.set(o,this[o]),delete this[o]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return Ao(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,i,o){this._$AK(e,o)}_$ET(e,i){let o=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,o);if(r!==void 0&&o.reflect===!0){let a=(o.converter?.toAttribute!==void 0?o.converter:ut).toAttribute(i,o.type);this._$Em=e,a==null?this.removeAttribute(r):this.setAttribute(r,a),this._$Em=null}}_$AK(e,i){let o=this.constructor,r=o._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let a=o.getPropertyOptions(r),n=typeof a.converter=="function"?{fromAttribute:a.converter}:a.converter?.fromAttribute!==void 0?a.converter:ut;this._$Em=r;let v=n.fromAttribute(i,a.type);this[r]=v??this._$Ej?.get(r)??v,this._$Em=null}}requestUpdate(e,i,o,r=!1,a){if(e!==void 0){let n=this.constructor;if(r===!1&&(a=this[e]),o??=n.getPropertyOptions(e),!((o.hasChanged??Ot)(a,i)||o.useDefault&&o.reflect&&a===this._$Ej?.get(e)&&!this.hasAttribute(n._$Eu(e,o))))return;this.C(e,i,o)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(e,i,{useDefault:o,reflect:r,wrapped:a},n){o&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,n??i??this[e]),a!==!0||n!==void 0)||(this._$AL.has(e)||(this.hasUpdated||o||(i=void 0),this._$AL.set(e,i)),r===!0&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(i){Promise.reject(i)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[r,a]of this._$Ep)this[r]=a;this._$Ep=void 0}let o=this.constructor.elementProperties;if(o.size>0)for(let[r,a]of o){let{wrapped:n}=a,v=this[r];n!==!0||this._$AL.has(r)||v===void 0||this.C(r,void 0,a,v)}}let e=!1,i=this._$AL;try{e=this.shouldUpdate(i),e?(this.willUpdate(i),this._$EO?.forEach(o=>o.hostUpdate?.()),this.update(i)):this._$EM()}catch(o){throw e=!1,this._$EM(),o}e&&this._$AE(i)}willUpdate(e){}_$AE(e){this._$EO?.forEach(i=>i.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(i=>this._$ET(i,this[i])),this._$EM()}updated(e){}firstUpdated(e){}};Ze.elementStyles=[],Ze.shadowRootOptions={mode:"open"},Ze[ht("elementProperties")]=new Map,Ze[ht("finalized")]=new Map,ja?.({ReactiveElement:Ze}),(Pt.reactiveElementVersions??=[]).push("2.1.2");var ao=globalThis,Bo=t=>t,Bt=ao.trustedTypes,To=Bt?Bt.createPolicy("lit-html",{createHTML:t=>t}):void 0,no="$lit$",Se=`lit$${Math.random().toFixed(9).slice(2)}$`,so="?"+Se,Na=`<${so}>`,Ue=document,mt=()=>Ue.createComment(""),ft=t=>t===null||typeof t!="object"&&typeof t!="function",lo=Array.isArray,jo=t=>lo(t)||typeof t?.[Symbol.iterator]=="function",io=`[ 	
\f\r]`,vt=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Eo=/-->/g,zo=/>/g,Ne=RegExp(`>|${io}(?:([^\\s"'>=/]+)(${io}*=${io}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Do=/'/g,Io=/"/g,No=/^(?:script|style|textarea|title)$/i,co=t=>(e,...i)=>({_$litType$:t,strings:e,values:i}),c=co(1),l=co(2),Fo=co(3),fe=Symbol.for("lit-noChange"),f=Symbol.for("lit-nothing"),Ro=new WeakMap,Fe=Ue.createTreeWalker(Ue,129);function Uo(t,e){if(!lo(t)||!t.hasOwnProperty("raw"))throw Error("invalid template strings array");return To!==void 0?To.createHTML(e):e}var Wo=(t,e)=>{let i=t.length-1,o=[],r,a=e===2?"<svg>":e===3?"<math>":"",n=vt;for(let v=0;v<i;v++){let u=t[v],m,b,g=-1,C=0;for(;C<u.length&&(n.lastIndex=C,b=n.exec(u),b!==null);)C=n.lastIndex,n===vt?b[1]==="!--"?n=Eo:b[1]!==void 0?n=zo:b[2]!==void 0?(No.test(b[2])&&(r=RegExp("</"+b[2],"g")),n=Ne):b[3]!==void 0&&(n=Ne):n===Ne?b[0]===">"?(n=r??vt,g=-1):b[1]===void 0?g=-2:(g=n.lastIndex-b[2].length,m=b[1],n=b[3]===void 0?Ne:b[3]==='"'?Io:Do):n===Io||n===Do?n=Ne:n===Eo||n===zo?n=vt:(n=Ne,r=void 0);let y=n===Ne&&t[v+1].startsWith("/>")?" ":"";a+=n===vt?u+Na:g>=0?(o.push(m),u.slice(0,g)+no+u.slice(g)+Se+y):u+Se+(g===-2?v:y)}return[Uo(t,a+(t[i]||"<?>")+(e===2?"</svg>":e===3?"</math>":"")),o]},gt=class t{constructor({strings:e,_$litType$:i},o){let r;this.parts=[];let a=0,n=0,v=e.length-1,u=this.parts,[m,b]=Wo(e,i);if(this.el=t.createElement(m,o),Fe.currentNode=this.el.content,i===2||i===3){let g=this.el.content.firstChild;g.replaceWith(...g.childNodes)}for(;(r=Fe.nextNode())!==null&&u.length<v;){if(r.nodeType===1){if(r.hasAttributes())for(let g of r.getAttributeNames())if(g.endsWith(no)){let C=b[n++],y=r.getAttribute(g).split(Se),H=/([.?@])?(.*)/.exec(C);u.push({type:1,index:a,name:H[2],strings:y,ctor:H[1]==="."?Et:H[1]==="?"?zt:H[1]==="@"?Dt:Ge}),r.removeAttribute(g)}else g.startsWith(Se)&&(u.push({type:6,index:a}),r.removeAttribute(g));if(No.test(r.tagName)){let g=r.textContent.split(Se),C=g.length-1;if(C>0){r.textContent=Bt?Bt.emptyScript:"";for(let y=0;y<C;y++)r.append(g[y],mt()),Fe.nextNode(),u.push({type:2,index:++a});r.append(g[C],mt())}}}else if(r.nodeType===8)if(r.data===so)u.push({type:2,index:a});else{let g=-1;for(;(g=r.data.indexOf(Se,g+1))!==-1;)u.push({type:7,index:a}),g+=Se.length-1}a++}}static createElement(e,i){let o=Ue.createElement("template");return o.innerHTML=e,o}};function We(t,e,i=t,o){if(e===fe)return e;let r=o!==void 0?i._$Co?.[o]:i._$Cl,a=ft(e)?void 0:e._$litDirective$;return r?.constructor!==a&&(r?._$AO?.(!1),a===void 0?r=void 0:(r=new a(t),r._$AT(t,i,o)),o!==void 0?(i._$Co??=[])[o]=r:i._$Cl=r),r!==void 0&&(e=We(t,r._$AS(t,e.values),r,o)),e}var Tt=class{constructor(e,i){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=i}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:i},parts:o}=this._$AD,r=(e?.creationScope??Ue).importNode(i,!0);Fe.currentNode=r;let a=Fe.nextNode(),n=0,v=0,u=o[0];for(;u!==void 0;){if(n===u.index){let m;u.type===2?m=new ot(a,a.nextSibling,this,e):u.type===1?m=new u.ctor(a,u.name,u.strings,this,e):u.type===6&&(m=new It(a,this,e)),this._$AV.push(m),u=o[++v]}n!==u?.index&&(a=Fe.nextNode(),n++)}return Fe.currentNode=Ue,r}p(e){let i=0;for(let o of this._$AV)o!==void 0&&(o.strings!==void 0?(o._$AI(e,o,i),i+=o.strings.length-2):o._$AI(e[i])),i++}},ot=class t{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,i,o,r){this.type=2,this._$AH=f,this._$AN=void 0,this._$AA=e,this._$AB=i,this._$AM=o,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,i=this._$AM;return i!==void 0&&e?.nodeType===11&&(e=i.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,i=this){e=We(this,e,i),ft(e)?e===f||e==null||e===""?(this._$AH!==f&&this._$AR(),this._$AH=f):e!==this._$AH&&e!==fe&&this._(e):e._$litType$!==void 0?this.$(e):e.nodeType!==void 0?this.T(e):jo(e)?this.k(e):this._(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==f&&ft(this._$AH)?this._$AA.nextSibling.data=e:this.T(Ue.createTextNode(e)),this._$AH=e}$(e){let{values:i,_$litType$:o}=e,r=typeof o=="number"?this._$AC(e):(o.el===void 0&&(o.el=gt.createElement(Uo(o.h,o.h[0]),this.options)),o);if(this._$AH?._$AD===r)this._$AH.p(i);else{let a=new Tt(r,this),n=a.u(this.options);a.p(i),this.T(n),this._$AH=a}}_$AC(e){let i=Ro.get(e.strings);return i===void 0&&Ro.set(e.strings,i=new gt(e)),i}k(e){lo(this._$AH)||(this._$AH=[],this._$AR());let i=this._$AH,o,r=0;for(let a of e)r===i.length?i.push(o=new t(this.O(mt()),this.O(mt()),this,this.options)):o=i[r],o._$AI(a),r++;r<i.length&&(this._$AR(o&&o._$AB.nextSibling,r),i.length=r)}_$AR(e=this._$AA.nextSibling,i){for(this._$AP?.(!1,!0,i);e!==this._$AB;){let o=Bo(e).nextSibling;Bo(e).remove(),e=o}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},Ge=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,i,o,r,a){this.type=1,this._$AH=f,this._$AN=void 0,this.element=e,this.name=i,this._$AM=r,this.options=a,o.length>2||o[0]!==""||o[1]!==""?(this._$AH=Array(o.length-1).fill(new String),this.strings=o):this._$AH=f}_$AI(e,i=this,o,r){let a=this.strings,n=!1;if(a===void 0)e=We(this,e,i,0),n=!ft(e)||e!==this._$AH&&e!==fe,n&&(this._$AH=e);else{let v=e,u,m;for(e=a[0],u=0;u<a.length-1;u++)m=We(this,v[o+u],i,u),m===fe&&(m=this._$AH[u]),n||=!ft(m)||m!==this._$AH[u],m===f?e=f:e!==f&&(e+=(m??"")+a[u+1]),this._$AH[u]=m}n&&!r&&this.j(e)}j(e){e===f?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??"")}},Et=class extends Ge{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===f?void 0:e}},zt=class extends Ge{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==f)}},Dt=class extends Ge{constructor(e,i,o,r,a){super(e,i,o,r,a),this.type=5}_$AI(e,i=this){if((e=We(this,e,i,0)??f)===fe)return;let o=this._$AH,r=e===f&&o!==f||e.capture!==o.capture||e.once!==o.once||e.passive!==o.passive,a=e!==f&&(o===f||r);r&&this.element.removeEventListener(this.name,this,o),a&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},It=class{constructor(e,i,o){this.element=e,this.type=6,this._$AN=void 0,this._$AM=i,this.options=o}get _$AU(){return this._$AM._$AU}_$AI(e){We(this,e)}},Go={M:no,P:Se,A:so,C:1,L:Wo,R:Tt,D:jo,V:We,I:ot,H:Ge,N:zt,U:Dt,B:Et,F:It},Fa=ao.litHtmlPolyfillSupport;Fa?.(gt,ot),(ao.litHtmlVersions??=[]).push("3.3.3");var qo=(t,e,i)=>{let o=i?.renderBefore??e,r=o._$litPart$;if(r===void 0){let a=i?.renderBefore??null;o._$litPart$=r=new ot(e.insertBefore(mt(),a),a,void 0,i??{})}return r._$AI(t),r};var po=globalThis,d=class extends Ze{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let i=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=qo(i,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return fe}};d._$litElement$=!0,d.finalized=!0,po.litElementHydrateSupport?.({LitElement:d});var Ua=po.litElementPolyfillSupport;Ua?.({LitElement:d});(po.litElementVersions??=[]).push("4.2.2");var Wa={attribute:!0,type:String,converter:ut,reflect:!1,hasChanged:Ot},Ga=(t=Wa,e,i)=>{let{kind:o,metadata:r}=i,a=globalThis.litPropertyMetadata.get(r);if(a===void 0&&globalThis.litPropertyMetadata.set(r,a=new Map),o==="setter"&&((t=Object.create(t)).wrapped=!0),a.set(i.name,t),o==="accessor"){let{name:n}=i;return{set(v){let u=e.get.call(this);e.set.call(this,v),this.requestUpdate(n,u,t,!0,v)},init(v){return v!==void 0&&this.C(n,void 0,t,v),v}}}if(o==="setter"){let{name:n}=i;return function(v){let u=this[n];e.call(this,v),this.requestUpdate(n,u,t,!0,v)}}throw Error("Unsupported decorator location: "+o)};function s(t){return(e,i)=>typeof i=="object"?Ga(t,e,i):((o,r,a)=>{let n=r.hasOwnProperty(a);return r.constructor.createProperty(a,o),n?Object.getOwnPropertyDescriptor(r,a):void 0})(t,e,i)}function re(t){return s({...t,state:!0,attribute:!1})}var ze=(t,e,i)=>(i.configurable=!0,i.enumerable=!0,Reflect.decorate&&typeof e!="object"&&Object.defineProperty(t,e,i),i);function Rt(t,e){return(i,o,r)=>{let a=n=>n.renderRoot?.querySelector(t)??null;if(e){let{get:n,set:v}=typeof o=="object"?i:r??(()=>{let u=Symbol();return{get(){return this[u]},set(m){this[u]=m}}})();return ze(i,o,{get(){let u=n.call(this);return u===void 0&&(u=a(this),(u!==null||this.hasUpdated)&&v.call(this,u)),u}})}return ze(i,o,{get(){return a(this)}})}}function Xo(t){return(e,i)=>{let{slot:o,selector:r}=t??{},a="slot"+(o?`[name=${o}]`:":not([name])");return ze(e,i,{get(){let n=this.renderRoot?.querySelector(a),v=n?.assignedElements(t)??[];return r===void 0?v:v.filter(u=>u.matches(r))}})}}var it={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},qe=t=>(...e)=>({_$litDirective$:t,values:e}),De=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,i,o){this._$Ct=e,this._$AM=i,this._$Ci=o}_$AS(e,i){return this.update(e,i)}update(e,i){return this.render(...i)}};var V=qe(class extends De{constructor(t){if(super(t),t.type!==it.ATTRIBUTE||t.name!=="class"||t.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t){return" "+Object.keys(t).filter(e=>t[e]).join(" ")+" "}update(t,[e]){if(this.st===void 0){this.st=new Set,t.strings!==void 0&&(this.nt=new Set(t.strings.join(" ").split(/\s/).filter(o=>o!=="")));for(let o in e)e[o]&&!this.nt?.has(o)&&this.st.add(o);return this.render(e)}let i=t.element.classList;for(let o of this.st)o in e||(i.remove(o),this.st.delete(o));for(let o in e){let r=!!e[o];r===this.st.has(o)||this.nt?.has(o)||(r?(i.add(o),this.st.add(o)):(i.remove(o),this.st.delete(o)))}return fe}});var Yo=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  height: var(--app-components-topbar-touch-target-size);
  padding: 0px var(--app-components-topbar-margin-global);
  user-select: none;

  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.wrapper:not(.inactive) {
    background: var(--container-global-color, #fcfcfc);
    box-shadow: var(--shadow-flat);
  }

.wrapper.tall {
    height: var(--app-components-topbar-touch-target-tall);
  }

.group {
  display: flex;
  align-items: center;
}

.group.right {
    justify-content: flex-end;
    flex-grow: 1;
  }

.settings .group.left > * {
    margin-right: 0;
    margin-left: 0;
  }

.group.left .title {
      padding-right: var(--app-components-topbar-label-spacing);
    }

.inactive .group.left {
    padding-left: var(--app-components-topbar-padding-left-small);
  }

.group.left .menu-button {
    margin-right: 0;
    margin-left: 0;
  }

.wide:is(.group.left .menu-button) {
      margin-left: 8px;
      margin-right: 8px;
    }

.group .app-icon {
    padding-right: var(--app-components-topbar-label-spacing);
    width: var(--app-components-topbar-icon-size);
    height: var(--app-components-topbar-icon-size);
    box-sizing: content-box;
    color: var(--element-neutral-color);
  }

.alert-container {
  display: flex;
  flex-grow: 1;
  gap: var(--app-components-topbar-label-spacing);
  align-items: center;
  justify-content: right;
}

.title {
  color: var(--element-active-color, #1a1a1a);
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.page-name {
  color: var(--element-active-color, #1a1a1a);
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.left-more-button {
  display: none;
}

.divider {
  width: 1px;
  height: var(--ui-components-divider-height-small);
  background: var(--border-divider-color);
}
`;var Jo=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  background: transparent;
  position: relative;
  min-height: var(--ui-components-button-touch-target-size);
  min-width: var(--ui-components-button-touch-target-size);
  padding: 0;

  appearance: none;
  border: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.wrapper .visible-wrapper {
    position: relative;
    height: var(--ui-components-icon-button-visual-target-size);
    width: var(--ui-components-icon-button-visual-target-size);
    border-radius: var(--ui-components-button-border-radius-top-left)
      var(--ui-components-button-border-radius-top-right)
      var(--ui-components-button-border-radius-bottom-right)
      var(--ui-components-button-border-radius-bottom-left);
    display: flex;
    align-items: center;
    justify-content: center;
  }

.wrapper.corner-left {
    align-items: flex-end;
    padding-right: 0;
  }

.wrapper.corner-left .visible-wrapper {
      width: calc(
        var(--ui-components-icon-button-visual-target-size) +
          var(--ui-components-icon-button-padding-right)
      );
      border-top-right-radius: 0;
      border-bottom-right-radius: 0;
    }

.wrapper.corner-right {
    align-items: flex-start;
    padding-left: 0;
  }

.wrapper.corner-right .visible-wrapper {
      width: calc(
        var(--ui-components-icon-button-visual-target-size) +
          var(--ui-components-icon-button-padding-left)
      );
      border-top-left-radius: 0;
      border-bottom-left-radius: 0;
    }

.wrapper.corner-left.corner-right .visible-wrapper {
      width: var(--ui-components-button-touch-target-size);
    }

.wrapper.wide .visible-wrapper {
    width: var(--ui-components-button-touch-target-size);
  }

.wrapper .icon {
    width: var(--ui-components-icon-button-icon-size);
    height: var(--ui-components-icon-button-icon-size);
  }

.wrapper .progress-spinner {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

.wrapper.has-label {
    padding: var(--ui-components-icon-button-padding-vertical) 0;
  }

.wrapper .label {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.wrapper.variant-normal {
            cursor: pointer;
}

.wrapper.variant-normal:focus {
            outline: none;
}

.wrapper.variant-normal .visible-wrapper {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper.variant-normal.activated .visible-wrapper {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-normal:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-normal:active .visible-wrapper {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.wrapper.variant-normal:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-normal:disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.variant-normal.disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.variant-normal:disabled {
            cursor: not-allowed;
}

.wrapper.variant-normal.disabled {
            cursor: not-allowed;
}

.wrapper.variant-normal {
    color: var(--on-normal-neutral-color);
}

.wrapper.variant-normal.active-color {
      color: var(--on-normal-active-color);
    }

.wrapper.variant-normal.activated .visible-wrapper {
      border-color: var(--normal-pressed-border-color);
      background-color: var(--normal-pressed-background-color);
    }

.wrapper.variant-flat {
            cursor: pointer;
}

.wrapper.variant-flat:focus {
            outline: none;
}

.wrapper.variant-flat .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.variant-flat.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-flat:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-flat:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.variant-flat:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-flat:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.variant-flat.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.variant-flat:disabled {
            cursor: not-allowed;
}

.wrapper.variant-flat.disabled {
            cursor: not-allowed;
}

.wrapper.variant-flat {
    color: var(--on-flat-neutral-color);
}

.wrapper.variant-flat.active-color {
      color: var(--on-flat-active-color);
    }

.wrapper.variant-raised {
            cursor: pointer;
}

.wrapper.variant-raised:focus {
            outline: none;
}

.wrapper.variant-raised .visible-wrapper {
            border-color: var(--raised-enabled-border-color);
            background-color: var(--raised-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--raised-enabled-border-color);
            --base-background-color: var(--raised-enabled-background-color);
}

.wrapper.variant-raised.activated .visible-wrapper {
            border-color: var(--raised-activated-border-color);
            background-color: var(--raised-activated-background-color);
            --base-border-color: var(--raised-activated-border-color);
            --base-background-color: var(--raised-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-raised:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--raised-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--raised-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-raised:active .visible-wrapper {
            border-color: var(--raised-pressed-border-color);
            background-color: var(--raised-pressed-background-color);
}

.wrapper.variant-raised:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-raised:disabled .visible-wrapper {
            border-color: var(--raised-disabled-border-color);
            background-color: var(--raised-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-raised-disabled-color) !important;
}

.wrapper.variant-raised.disabled .visible-wrapper {
            border-color: var(--raised-disabled-border-color);
            background-color: var(--raised-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-raised-disabled-color) !important;
}

.wrapper.variant-raised:disabled {
            cursor: not-allowed;
}

.wrapper.variant-raised.disabled {
            cursor: not-allowed;
}

.wrapper.variant-raised {
    color: var(--on-raised-active-color);
}

.wrapper.variant-raised.active-color {
      color: var(--on-raised-active-color);
    }

.wrapper.variant-integration {
            cursor: pointer;
}

.wrapper.variant-integration:focus {
            outline: none;
}

.wrapper.variant-integration .visible-wrapper {
            border-color: var(--integration-normal-enabled-border-color);
            background-color: var(--integration-normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--integration-normal-enabled-border-color);
            --base-background-color: var(--integration-normal-enabled-background-color);
}

.wrapper.variant-integration.activated .visible-wrapper {
            border-color: var(--integration-normal-activated-border-color);
            background-color: var(--integration-normal-activated-background-color);
            --base-border-color: var(--integration-normal-activated-border-color);
            --base-background-color: var(--integration-normal-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-integration:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--integration-normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--integration-normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-integration:active .visible-wrapper {
            border-color: var(--integration-normal-pressed-border-color);
            background-color: var(--integration-normal-pressed-background-color);
}

.wrapper.variant-integration:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-integration:disabled .visible-wrapper {
            border-color: var(--integration-normal-disabled-border-color);
            background-color: var(--integration-normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-normal-disabled-color) !important;
}

.wrapper.variant-integration.disabled .visible-wrapper {
            border-color: var(--integration-normal-disabled-border-color);
            background-color: var(--integration-normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-normal-disabled-color) !important;
}

.wrapper.variant-integration:disabled {
            cursor: not-allowed;
}

.wrapper.variant-integration.disabled {
            cursor: not-allowed;
}

.wrapper.variant-integration {
    color: var(--integration-on-normal-neutral-color);
}

.wrapper.variant-integration .visible-wrapper {
      border: 0;
    }
`;var h=t=>(e,i)=>{if(i!==void 0)i.addInitializer(()=>{customElements.get(t)||customElements.define(t,e)});else{if(customElements.get(t))return;customElements.define(t,e)}};var qa=Object.defineProperty,Xa=Object.getOwnPropertyDescriptor,we=(t,e,i,o)=>{for(var r=o>1?void 0:o?Xa(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&qa(e,i,r),r};var le=class extends d{constructor(){super(...arguments),this.variant="normal",this.activated=!1,this.cornerLeft=!1,this.cornerRight=!1,this.activeColor=!1,this.wide=!1,this.disabled=!1,this.progress=void 0,this.hasLabel=!1}get progressSpinner(){if(this.progress===void 0)return f;if(this.progress===100)return c`<div class="progress-spinner">
        <svg
          width="40"
          height="40"
          viewBox="0 0 40 40"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            cx="20"
            cy="20"
            r="18"
            stroke="#325B9A"
            stroke-width="4"
            fill="none"
          />
        </svg>
      </div>`;let t=this.progress*.95*3.6*Math.PI/180,e=20+18*Math.sin(t),i=20-18*Math.cos(t),o=t>Math.PI?1:0;return c`<div class="progress-spinner">
      <svg
        width="40"
        height="40"
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle
          cx="20"
          cy="20"
          r="18"
          stroke="var(--container-backdrop-color)"
          stroke-width="4"
          fill="none"
        />
        <path
          d="M18 2 A18 18 0 ${o} 1 ${e} ${i}"
          stroke="var(--instrument-enhanced-secondary-color)"
          stroke-width="4"
          stroke-linecap="round"
        />
      </svg>
    </div>`}render(){return c`
      <button
        class=${V({wrapper:!0,["variant-"+this.variant]:!0,activated:this.activated,"corner-left":this.cornerLeft,"corner-right":this.cornerRight,"active-color":this.activeColor,"has-label":this.hasLabel,wide:this.wide,progress:this.progress!==void 0})}
        ?disabled=${this.disabled}
        part="wrapper"
      >
        ${this.progress!==void 0?this.progressSpinner:f}
        <div class="visible-wrapper" part="visible-wrapper">
          <div class="icon" part="icon">
            <slot></slot>
          </div>
        </div>
        ${this.hasLabel?c`<div class="label" part="label">
              <slot name="label"></slot>
            </div>`:f}
      </button>
    `}};le.styles=x(Jo);we([s({type:String})],le.prototype,"variant",2);we([s({type:Boolean})],le.prototype,"activated",2);we([s({type:Boolean})],le.prototype,"cornerLeft",2);we([s({type:Boolean})],le.prototype,"cornerRight",2);we([s({type:Boolean})],le.prototype,"activeColor",2);we([s({type:Boolean})],le.prototype,"wide",2);we([s({type:Boolean})],le.prototype,"disabled",2);we([s({type:Number})],le.prototype,"progress",2);we([s({type:Boolean})],le.prototype,"hasLabel",2);le=we([h("obc-icon-button")],le);var Qo=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  padding: 0;
}

* {
  box-sizing: border-box;
}

.clock {
  display: flex;
  align-items: center;
  color: var(--element-active-color);
  text-align: center;
  gap: var(--app-components-clock-digit-spacing);
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-button-font-weight);
  font-size: var(--global-typography-ui-button-font-size);
  line-height: var(--global-typography-ui-button-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.integration-bar-mode .clock {
  color: var(--integration-on-normal-active-color);
}

.blink {
  display: none;
}

@keyframes ticks {
  from {
    opacity: 1;
  }

  50% {
    opacity: 0;
  }

  to {
    opacity: 1;
  }
}

.ticks {
  width: var(--app-components-clock-colon-size);
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--app-components-clock-colon-spacing);
}

.ticks.animate {
    animation: ticks 1s linear infinite;
  }

.blink .ticks {
    width: 16px;
    padding: 0;
  }

.ticks .tick {
    width: 100%;
    height: 100%;
    width: calc(var(--app-components-clock-colon-size) + 1px);
    height: calc(var(--app-components-clock-colon-size) + 1px);
    border-radius: 100%;
    background-color: var(--element-active-color);
  }

.integration-bar-mode .ticks .tick {
  background-color: var(--integration-on-normal-active-color);
}

.blink-wrapper {
  display: none;
  height: var(--app-components-clock-touch-target);
  width: 24px;
  align-items: center;
  justify-content: center;
}

.timezone {
  color: var(--element-neutral-color);
  text-align: center;

  font-family: var(--font-family-main);

  font-weight: var(--global-typography-ui-body-font-weight);

  font-size: var(--global-typography-ui-body-font-size);

  line-height: var(--global-typography-ui-body-line-height);

  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.integration-bar-mode .timezone {
  color: var(--integration-on-normal-active-color);
}

.date {
  text-align: center;
  color: var(--element-active-color);
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.integration-bar-mode .date {
  color: var(--integration-on-normal-active-color);
}

.wrapper {
  user-select: none;
  display: flex;
  align-items: center;
  padding: 0 var(--app-components-clock-margin-horizontal);
  appearance: none;
  border: none;
  background: none;
  height: var(--app-components-clock-touch-target);
}

.wrapper:not(.no-click) {
            cursor: pointer;
}

.wrapper:not(.no-click):focus {
            outline: none;
}

.wrapper:not(.no-click) .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.activated:not(.no-click) .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper:not(.no-click):hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:not(.no-click):active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper:not(.no-click):focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:not(.no-click):disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.disabled:not(.no-click) .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper:not(.no-click):disabled {
            cursor: not-allowed;
}

.wrapper.disabled:not(.no-click) {
            cursor: not-allowed;
}

.wrapper.selected {
            cursor: pointer;
}

.wrapper.selected:focus {
            outline: none;
}

.wrapper.selected .visible-wrapper {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

.wrapper.selected.activated .visible-wrapper {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

.wrapper.selected:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.selected:active .visible-wrapper {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

.wrapper.selected:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.selected:disabled .visible-wrapper {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.wrapper.selected.disabled .visible-wrapper {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.wrapper.selected:disabled {
            cursor: not-allowed;
}

.wrapper.selected.disabled {
            cursor: not-allowed;
}

.wrapper.double {
    height: var(--app-components-clock-touch-target-size-double);
  }

.visible-wrapper {
  display: flex;
  align-items: center;
  border-radius: var(--app-components-clock-border-radius);
  padding: 0 var(--app-components-clock-padding-horizontal);
  height: var(--app-components-clock-visual-target);
  gap: var(--app-components-clock-label-spacing);
  border: 1px solid transparent;
}

.double .visible-wrapper {
    flex-direction: column;
    height: 48px;
    gap: 0;
  }

.divider {
  width: 1px;
  height: 16px;
  background-color: var(--border-divider-color);
}

.integration-bar-mode .divider {
  background-color: var(--integration-border-outline);
}

.double .divider {
  display: none;
}

.row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--app-components-clock-label-spacing);
}
`;var e1=Symbol.for(""),Ya=t=>{if(t?.r===e1)return t?._$litStatic$};var R=(t,...e)=>({_$litStatic$:e.reduce((i,o,r)=>i+(a=>{if(a._$litStatic$!==void 0)return a._$litStatic$;throw Error(`Value passed to 'literal' function must be a 'literal' result: ${a}. Use 'unsafeStatic' to pass non-literal values, but
            take care to ensure page security.`)})(o)+t[r+1],t[0]),r:e1}),Ko=new Map,ho=t=>(e,...i)=>{let o=i.length,r,a,n=[],v=[],u,m=0,b=!1;for(;m<o;){for(u=e[m];m<o&&(a=i[m],(r=Ya(a))!==void 0);)u+=r+e[++m],b=!0;m!==o&&v.push(a),n.push(u),m++}if(m===o&&n.push(e[o]),b){let g=n.join("$$lit$$");(e=Ko.get(g))===void 0&&(n.raw=n,Ko.set(g,e=n)),i=v}return t(e,...i)},_=ho(c),x5=ho(l),H5=ho(Fo);var Ja=Object.defineProperty,Qa=Object.getOwnPropertyDescriptor,K=(t,e,i,o)=>{for(var r=o>1?void 0:o?Qa(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ja(e,i,r),r},G=class extends d{constructor(){super(...arguments),this.showSeconds=!1,this.showDate=!1,this.showTimezone=!1,this.timeZoneOffsetHours=0,this.isClickable=!0,this.showYear=!1,this.showWeekday=!1,this.locale="en-GB",this.hour12=!1,this.selected=!1,this.double=!1,this.activated=!1,this.integrationBarMode=!1,this.blinkOnlyBreakpointPx=0}get timezoneString(){return this.timeZoneOffsetHours===0?"UTC":this.timeZoneOffsetHours>0?`UTC+${this.timeZoneOffsetHours}`:`UTC-${-this.timeZoneOffsetHours}`}_dateString(t){let e={month:"short",day:"numeric",weekday:this.showWeekday?"short":void 0,year:this.showYear?"numeric":void 0,timeZone:"UTC"};return t.toLocaleDateString(this.locale,e).replace(/,/g,"").replace(/\./g,"")}_ampm(t){return this.hour12?t<12?" AM":" PM":""}render(){let t=new Date(this.date);t.setUTCHours(t.getUTCHours()+this.timeZoneOffsetHours);let e=t.getUTCHours(),i=t.getUTCMinutes(),o=this.hour12?e%12:e,r=o<10?`0${o}`:`${o}`,a=i<10?`0${i}`:`${i}`,n=t.getUTCSeconds(),v=n<10?`0${n}`:`${n}`,u=this._ampm(e),m=this._dateString(t),b=this.isClickable?R`button`:R`div`,g=_`<div class="ticks ${this.showSeconds?"":"animate"}">
      <span class="tick"></span><span class="tick"></span>
    </div>`,C=`@media (max-width: ${this.blinkOnlyBreakpointPx}px )`,y=_`<div class="clock">
        ${r}${g}${a}${this.showSeconds?_`${g}${v}`:""}${u}
      </div>

      ${this.showTimezone?_`<div class="timezone">${this.timezoneString}</div>`:null}`;return _`
      <style>
        ${C} {
          .wrapper {
            display: none !important;
          }
          .blink-wrapper {
            display: flex !important;
          }
        }
      </style>
      <${b} 
        class=${V({wrapper:!0,"no-click":!this.isClickable,selected:this.selected,double:this.double,"integration-bar-mode":this.integrationBarMode,activated:this.activated})}>
        <div class="visible-wrapper">
          ${this.double?_`<div class="row">${y}</div>`:y}
        ${this.showDate?_` <div class="divider"></div>
                <div class="date">${m}</div>`:f}
        ${this.double?_`</div>`:f}
        </div>
      </${b}>
      <div class=${V({"blink-wrapper":!0,clock:!0,blink:!0,"integration-bar-mode":this.integrationBarMode})}>
        <div class="ticks animate"><div class="tick"></div><div class="tick"></div></div>
      </div>
    `}};G.styles=x(Qo);K([s({type:String})],G.prototype,"date",2);K([s({type:Boolean})],G.prototype,"showSeconds",2);K([s({type:Boolean})],G.prototype,"showDate",2);K([s({type:Boolean})],G.prototype,"showTimezone",2);K([s({type:Number})],G.prototype,"timeZoneOffsetHours",2);K([s({type:Boolean,attribute:!1})],G.prototype,"isClickable",2);K([s({type:Boolean})],G.prototype,"showYear",2);K([s({type:Boolean})],G.prototype,"showWeekday",2);K([s({type:String})],G.prototype,"locale",2);K([s({type:Boolean})],G.prototype,"hour12",2);K([s({type:Boolean})],G.prototype,"selected",2);K([s({type:Boolean})],G.prototype,"double",2);K([s({type:Boolean})],G.prototype,"activated",2);K([s({type:Boolean})],G.prototype,"integrationBarMode",2);K([s({type:Number})],G.prototype,"blinkOnlyBreakpointPx",2);G=K([h("obc-clock")],G);var t1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }
:host {
  width: 1px;
  height: 24px;
  flex-shrink: 0;
  border-radius: 1px;
  background: var(--border-divider-color, rgba(0, 0, 0, 0.08));
}
`;var Ka=Object.getOwnPropertyDescriptor,en=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ka(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=n(r)||r);return r},uo=class extends d{render(){return c``}};uo.styles=x(t1);uo=en([h("obc-divider")],uo);var r1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

ol {
  padding: 0 var(--app-components-breadcrumbs-padding-horizontal);
  margin: 0;
  list-style-type: none;
  display: flex;
  user-select: none;
}

li {
  display: flex;
  align-items: center;
  color: var(--on-flat-neutral-color);
}

li .label-wrapper {
    color: var(--on-flat-neutral-color);
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-body-font-weight);
    font-size: var(--global-typography-ui-body-font-size);
    line-height: var(--global-typography-ui-body-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    display: flex;
    align-items: center;
    justify-content: center;
    height: var(--app-components-breadcrumb-item-touch-target-size);
    margin: 0;
    padding: 0;
    border: none;
    background: none;
  }

:is(li .label-wrapper):not(.active) {
            cursor: pointer;
}

:is(li .label-wrapper):not(.active):focus {
            outline: none;
}

:is(li .label-wrapper):not(.active) .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.activated:is(li .label-wrapper):not(.active) .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

:is(li .label-wrapper):not(.active):hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(li .label-wrapper):not(.active):active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

:is(li .label-wrapper):not(.active):focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(li .label-wrapper):not(.active):disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.disabled:is(li .label-wrapper):not(.active) .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

:is(li .label-wrapper):not(.active):disabled {
            cursor: not-allowed;
}

.disabled:is(li .label-wrapper):not(.active) {
            cursor: not-allowed;
}

li .visible-wrapper {
    display: flex;
    height: var(--app-components-breadcrumb-item-visual-target-size);
    padding: 0 var(--app-components-breadcrumb-item-padding-horizontal);
    align-items: center;
    gap: var(--app-components-breadcrumb-item-label-spacing);
    border-radius: var(--app-components-breadcrumb-item-border-radius);
  }

li .active {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-flat-active-color);
  }

.divider {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--app-components-breadcrumb-item-chevron-container-size);
}

.divider .icon {
    display: block;
    width: var(--app-components-breadcrumb-item-icon-size);
    height: var(--app-components-breadcrumb-item-icon-size);
    flex-shrink: 0;
  }
`;var tn=Object.defineProperty,rn=Object.getOwnPropertyDescriptor,o1=(t,e,i,o)=>{for(var r=o>1?void 0:o?rn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&tn(e,i,r),r},jt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8.59009 7.41L10.0001 6L16.0001 12L10.0001 18L8.59009 16.59L13.1701 12L8.59009 7.41Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.59009 7.41L10.0001 6L16.0001 12L10.0001 18L8.59009 16.59L13.1701 12L8.59009 7.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};jt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;o1([s({type:Boolean})],jt.prototype,"useCssColor",2);jt=o1([h("obi-chevron-right-google")],jt);var on=Object.defineProperty,an=Object.getOwnPropertyDescriptor,vo=(t,e,i,o)=>{for(var r=o>1?void 0:o?an(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&on(e,i,r),r},bt=class extends d{constructor(){super(...arguments),this.items=[],this.iconOnly=!1}render(){return c`
      <nav aria-label="Breadcrumb" class="breadcrumb">
        <ol>
          ${this.items.map((t,e)=>{let i=e===this.items.length-1;return c`
              <li>
                ${e>0?c`<span class="divider">
                      <obi-chevron-right-google class="icon">
                      </obi-chevron-right-google>
                    </span>`:f}
                ${i?c` <div class="label-wrapper active">
                      <div class="visible-wrapper">
                        ${t.icon?t.icon():f}
                        ${this.iconOnly&&!i?f:c`<span class="label">${t.label}</span>`}
                      </div>
                    </div>`:c` <button
                      role="link"
                      @click=${()=>this.handleClick(t)}
                      class="label-wrapper"
                    >
                      <div class="visible-wrapper">
                        ${t.icon?t.icon():f}
                        ${this.iconOnly&&!i?f:c`<span class="label">${t.label}</span>`}
                      </div>
                    </button>`}
              </li>
            `})}
        </ol>
      </nav>
    `}handleClick(t){this.dispatchEvent(new CustomEvent("breadcrumb-click",{detail:t}))}};bt.styles=x(r1);vo([s({attribute:!1})],bt.prototype,"items",2);vo([s({attribute:!1})],bt.prototype,"iconOnly",2);bt=vo([h("obc-breadcrumb")],bt);var nn=Object.defineProperty,sn=Object.getOwnPropertyDescriptor,i1=(t,e,i,o)=>{for(var r=o>1?void 0:o?sn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&nn(e,i,r),r},Nt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M3 13H21V11H3V13Z" fill="currentColor"/>
<path d="M3 18H21V16H3V18Z" fill="currentColor"/>
<path d="M3 6V8H21V6H3Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M3 13H21V11H3V13Z" style="fill: var(--element-active-color)"/>
<path d="M3 18H21V16H3V18Z" style="fill: var(--element-active-color)"/>
<path d="M3 6V8H21V6H3Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Nt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;i1([s({type:Boolean})],Nt.prototype,"useCssColor",2);Nt=i1([h("obi-menu-iec")],Nt);var ln=Object.defineProperty,cn=Object.getOwnPropertyDescriptor,a1=(t,e,i,o)=>{for(var r=o>1?void 0:o?cn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&ln(e,i,r),r},Ft=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M6 19H9V13H15V19H18V10L12 5.5L6 10V19ZM4 21V9L12 3L20 9V21H13V15H11V21H4Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M6 19H9V13H15V19H18V10L12 5.5L6 10V19ZM4 21V9L12 3L20 9V21H13V15H11V21H4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ft.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;a1([s({type:Boolean})],Ft.prototype,"useCssColor",2);Ft=a1([h("obi-home")],Ft);var dn=Object.defineProperty,pn=Object.getOwnPropertyDescriptor,n1=(t,e,i,o)=>{for(var r=o>1?void 0:o?pn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&dn(e,i,r),r},Ut=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ut.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;n1([s({type:Boolean})],Ut.prototype,"useCssColor",2);Ut=n1([h("obi-close-google")],Ut);var hn=Object.defineProperty,un=Object.getOwnPropertyDescriptor,s1=(t,e,i,o)=>{for(var r=o>1?void 0:o?un(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&hn(e,i,r),r},Wt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7.83 11H20V13H7.83L13.41 18.59L12 20L4 12L12 4L13.42 5.41L7.83 11Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.83 11H20V13H7.83L13.41 18.59L12 20L4 12L12 4L13.42 5.41L7.83 11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Wt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;s1([s({type:Boolean})],Wt.prototype,"useCssColor",2);Wt=s1([h("obi-arrow-left-google")],Wt);var vn=Object.defineProperty,mn=Object.getOwnPropertyDescriptor,l1=(t,e,i,o)=>{for(var r=o>1?void 0:o?mn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&vn(e,i,r),r},Gt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 4L10.59 5.41L16.17 11H4V13H16.17L10.59 18.59L12 20L20 12L12 4Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 4L10.59 5.41L16.17 11H4V13H16.17L10.59 18.59L12 20L20 12L12 4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Gt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;l1([s({type:Boolean})],Gt.prototype,"useCssColor",2);Gt=l1([h("obi-arrow-right-google")],Gt);var fn=Object.defineProperty,gn=Object.getOwnPropertyDescriptor,c1=(t,e,i,o)=>{for(var r=o>1?void 0:o?gn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&fn(e,i,r),r},qt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99976 11.9999C6.99976 10.6738 7.52654 9.40202 8.46422 8.46434C9.4019 7.52666 10.6737 6.99988 11.9998 6.99988C13.3258 6.99988 14.5976 7.52666 15.5353 8.46434L16.2424 9.17145L9.17133 16.2425L8.46422 15.5354C7.52654 14.5977 6.99976 13.326 6.99976 11.9999ZM9.87843 9.87856C9.31583 10.4412 8.99976 11.2042 8.99976 11.9999C8.99976 12.4516 9.10163 12.8928 9.29265 13.2928L13.2926 9.29277C12.8927 9.10175 12.4515 8.99988 11.9998 8.99988C11.2041 8.99988 10.441 9.31595 9.87843 9.87856Z" fill="currentColor"/>
<path d="M3.51447 19.0709L6.3429 16.2425L7.75711 17.6567L4.92869 20.4852L3.51447 19.0709Z" fill="currentColor"/>
<path d="M0.999756 10.9999H4.99976V12.9999H0.999756V10.9999Z" fill="currentColor"/>
<path d="M4.92874 3.51462L7.75717 6.34304L6.34295 7.75726L3.51453 4.92883L4.92874 3.51462Z" fill="currentColor"/>
<path d="M12.9998 0.999878V4.99988H10.9998V0.999878H12.9998Z" fill="currentColor"/>
<path d="M20.4851 4.92878L17.6567 7.75721L16.2425 6.343L19.0709 3.51457L20.4851 4.92878Z" fill="currentColor"/>
<path d="M20.1539 11C20.8 11 21.4154 11.088 22 11.253C19.5016 11.9515 17.6924 14.036 17.6924 16.5C17.6924 18.964 19.5016 21.0485 22 21.747C21.4154 21.912 20.8 22 20.1539 22C16.757 22 14 19.536 14 16.5C14 13.464 16.757 11 20.1539 11Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99976 11.9999C6.99976 10.6738 7.52654 9.40202 8.46422 8.46434C9.4019 7.52666 10.6737 6.99988 11.9998 6.99988C13.3258 6.99988 14.5976 7.52666 15.5353 8.46434L16.2424 9.17145L9.17133 16.2425L8.46422 15.5354C7.52654 14.5977 6.99976 13.326 6.99976 11.9999ZM9.87843 9.87856C9.31583 10.4412 8.99976 11.2042 8.99976 11.9999C8.99976 12.4516 9.10163 12.8928 9.29265 13.2928L13.2926 9.29277C12.8927 9.10175 12.4515 8.99988 11.9998 8.99988C11.2041 8.99988 10.441 9.31595 9.87843 9.87856Z" style="fill: var(--element-active-color)"/>
<path d="M3.51447 19.0709L6.3429 16.2425L7.75711 17.6567L4.92869 20.4852L3.51447 19.0709Z" style="fill: var(--element-active-color)"/>
<path d="M0.999756 10.9999H4.99976V12.9999H0.999756V10.9999Z" style="fill: var(--element-active-color)"/>
<path d="M4.92874 3.51462L7.75717 6.34304L6.34295 7.75726L3.51453 4.92883L4.92874 3.51462Z" style="fill: var(--element-active-color)"/>
<path d="M12.9998 0.999878V4.99988H10.9998V0.999878H12.9998Z" style="fill: var(--element-active-color)"/>
<path d="M20.4851 4.92878L17.6567 7.75721L16.2425 6.343L19.0709 3.51457L20.4851 4.92878Z" style="fill: var(--element-active-color)"/>
<path d="M20.1539 11C20.8 11 21.4154 11.088 22 11.253C19.5016 11.9515 17.6924 14.036 17.6924 16.5C17.6924 18.964 19.5016 21.0485 22 21.747C21.4154 21.912 20.8 22 20.1539 22C16.757 22 14 19.536 14 16.5C14 13.464 16.757 11 20.1539 11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};qt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;c1([s({type:Boolean})],qt.prototype,"useCssColor",2);qt=c1([h("obi-palette-day-night-iec")],qt);var bn=Object.defineProperty,Cn=Object.getOwnPropertyDescriptor,d1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Cn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&bn(e,i,r),r},Xt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M4 8H8V4H4V8ZM10 20H14V16H10V20ZM4 20H8V16H4V20ZM4 14H8V10H4V14ZM10 14H14V10H10V14ZM16 4V8H20V4H16ZM10 8H14V4H10V8ZM16 14H20V10H16V14ZM16 20H20V16H16V20Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M4 8H8V4H4V8ZM10 20H14V16H10V20ZM4 20H8V16H4V20ZM4 14H8V10H4V14ZM10 14H14V10H10V14ZM16 4V8H20V4H16ZM10 8H14V4H10V8ZM16 14H20V10H16V14ZM16 20H20V16H16V20Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Xt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;d1([s({type:Boolean})],Xt.prototype,"useCssColor",2);Xt=d1([h("obi-applications")],Xt);var yn=Object.defineProperty,wn=Object.getOwnPropertyDescriptor,p1=(t,e,i,o)=>{for(var r=o>1?void 0:o?wn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&yn(e,i,r),r},Yt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M14 6C14 4.9 13.1 4 12 4C10.9 4 10 4.9 10 6C10 7.1 10.9 8 12 8C13.1 8 14 7.1 14 6Z" fill="currentColor"/>
<path d="M14 12C14 10.9 13.1 10 12 10C10.9 10 10 10.9 10 12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12Z" fill="currentColor"/>
<path d="M14 18C14 16.9 13.1 16 12 16C10.9 16 10 16.9 10 18C10 19.1 10.9 20 12 20C13.1 20 14 19.1 14 18Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14 6C14 4.9 13.1 4 12 4C10.9 4 10 4.9 10 6C10 7.1 10.9 8 12 8C13.1 8 14 7.1 14 6Z" style="fill: var(--element-active-color)"/>
<path d="M14 12C14 10.9 13.1 10 12 10C10.9 10 10 10.9 10 12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12Z" style="fill: var(--element-active-color)"/>
<path d="M14 18C14 16.9 13.1 16 12 16C10.9 16 10 16.9 10 18C10 19.1 10.9 20 12 20C13.1 20 14 19.1 14 18Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Yt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;p1([s({type:Boolean})],Yt.prototype,"useCssColor",2);Yt=p1([h("obi-more-vertical-google")],Yt);var Ln=Object.defineProperty,kn=Object.getOwnPropertyDescriptor,h1=(t,e,i,o)=>{for(var r=o>1?void 0:o?kn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ln(e,i,r),r},Jt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5.85 17.1C6.7 16.45 7.65 15.9375 8.7 15.5625C9.75 15.1875 10.85 15 12 15C13.15 15 14.25 15.1875 15.3 15.5625C16.35 15.9375 17.3 16.45 18.15 17.1C18.7333 16.4167 19.1875 15.6417 19.5125 14.775C19.8375 13.9083 20 12.9833 20 12C20 9.78333 19.2208 7.89583 17.6625 6.3375C16.1042 4.77917 14.2167 4 12 4C9.78333 4 7.89583 4.77917 6.3375 6.3375C4.77917 7.89583 4 9.78333 4 12C4 12.9833 4.1625 13.9083 4.4875 14.775C4.8125 15.6417 5.26667 16.4167 5.85 17.1ZM12 13C11.0167 13 10.1875 12.6625 9.5125 11.9875C8.8375 11.3125 8.5 10.4833 8.5 9.5C8.5 8.51667 8.8375 7.6875 9.5125 7.0125C10.1875 6.3375 11.0167 6 12 6C12.9833 6 13.8125 6.3375 14.4875 7.0125C15.1625 7.6875 15.5 8.51667 15.5 9.5C15.5 10.4833 15.1625 11.3125 14.4875 11.9875C13.8125 12.6625 12.9833 13 12 13ZM12 22C10.6167 22 9.31667 21.7375 8.1 21.2125C6.88333 20.6875 5.825 19.975 4.925 19.075C4.025 18.175 3.3125 17.1167 2.7875 15.9C2.2625 14.6833 2 13.3833 2 12C2 10.6167 2.2625 9.31667 2.7875 8.1C3.3125 6.88333 4.025 5.825 4.925 4.925C5.825 4.025 6.88333 3.3125 8.1 2.7875C9.31667 2.2625 10.6167 2 12 2C13.3833 2 14.6833 2.2625 15.9 2.7875C17.1167 3.3125 18.175 4.025 19.075 4.925C19.975 5.825 20.6875 6.88333 21.2125 8.1C21.7375 9.31667 22 10.6167 22 12C22 13.3833 21.7375 14.6833 21.2125 15.9C20.6875 17.1167 19.975 18.175 19.075 19.075C18.175 19.975 17.1167 20.6875 15.9 21.2125C14.6833 21.7375 13.3833 22 12 22Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5.85 17.1C6.7 16.45 7.65 15.9375 8.7 15.5625C9.75 15.1875 10.85 15 12 15C13.15 15 14.25 15.1875 15.3 15.5625C16.35 15.9375 17.3 16.45 18.15 17.1C18.7333 16.4167 19.1875 15.6417 19.5125 14.775C19.8375 13.9083 20 12.9833 20 12C20 9.78333 19.2208 7.89583 17.6625 6.3375C16.1042 4.77917 14.2167 4 12 4C9.78333 4 7.89583 4.77917 6.3375 6.3375C4.77917 7.89583 4 9.78333 4 12C4 12.9833 4.1625 13.9083 4.4875 14.775C4.8125 15.6417 5.26667 16.4167 5.85 17.1ZM12 13C11.0167 13 10.1875 12.6625 9.5125 11.9875C8.8375 11.3125 8.5 10.4833 8.5 9.5C8.5 8.51667 8.8375 7.6875 9.5125 7.0125C10.1875 6.3375 11.0167 6 12 6C12.9833 6 13.8125 6.3375 14.4875 7.0125C15.1625 7.6875 15.5 8.51667 15.5 9.5C15.5 10.4833 15.1625 11.3125 14.4875 11.9875C13.8125 12.6625 12.9833 13 12 13ZM12 22C10.6167 22 9.31667 21.7375 8.1 21.2125C6.88333 20.6875 5.825 19.975 4.925 19.075C4.025 18.175 3.3125 17.1167 2.7875 15.9C2.2625 14.6833 2 13.3833 2 12C2 10.6167 2.2625 9.31667 2.7875 8.1C3.3125 6.88333 4.025 5.825 4.925 4.925C5.825 4.025 6.88333 3.3125 8.1 2.7875C9.31667 2.2625 10.6167 2 12 2C13.3833 2 14.6833 2.2625 15.9 2.7875C17.1167 3.3125 18.175 4.025 19.075 4.925C19.975 5.825 20.6875 6.88333 21.2125 8.1C21.7375 9.31667 22 10.6167 22 12C22 13.3833 21.7375 14.6833 21.2125 15.9C20.6875 17.1167 19.975 18.175 19.075 19.075C18.175 19.975 17.1167 20.6875 15.9 21.2125C14.6833 21.7375 13.3833 22 12 22Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Jt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;h1([s({type:Boolean})],Jt.prototype,"useCssColor",2);Jt=h1([h("obi-user")],Jt);var Mn=Object.defineProperty,xn=Object.getOwnPropertyDescriptor,z=(t,e,i,o)=>{for(var r=o>1?void 0:o?xn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Mn(e,i,r),r};var T=class extends d{constructor(){super(...arguments),this.appTitle="App",this.pageName="Page",this.menuButtonIcon="menu",this.menuButtonActivated=!1,this.dimmingButtonActivated=!1,this.appsButtonActivated=!1,this.leftMoreButtonActivated=!1,this.userButtonActivated=!1,this.userButtonDisabled=!1,this.tall=!1,this.wideMenuButton=!1,this.showAppsButton=!1,this.showDimmingButton=!1,this.showUserButton=!1,this.showClock=!1,this.showDate=!1,this.showAppIcon=!1,this.inactive=!1,this.appButtonBreakpointPx=500,this.dimmingButtonBreakpointPx=500,this.appTitleBreakpointPx=500,this.userButtonBreakpointPx=500,this.appIconBreakpointPx=500,this.settings=!1,this.breadcrumbItems=[],this.leftButtonEvent=null,this.leftButtonTimeout=null,this.isLeftButtonDown=!1,this.isEmergencyBrightness=!1}dimmingButtonClicked(){this.dispatchEvent(new CustomEvent("dimming-button-clicked"))}appsButtonClicked(){this.dispatchEvent(new CustomEvent("apps-button-clicked"))}leftMoreButtonClicked(){this.dispatchEvent(new CustomEvent("left-more-button-clicked"))}userButtonClicked(){this.dispatchEvent(new CustomEvent("user-button-clicked"))}leftButtonDown(t){this.leftButtonEvent=t,this.isLeftButtonDown=!0,this.leftButtonTimeout=setTimeout(()=>{this.leftButtonEvent=null,this.dispatchEvent(new CustomEvent("emergency-brightness-start")),this.isEmergencyBrightness=!0},500)}leftButtonUp(){this.leftButtonEvent&&(this.dispatchEvent(this.leftButtonEvent),this.leftButtonEvent=null),this.leftButtonTimeout&&(clearTimeout(this.leftButtonTimeout),this.leftButtonTimeout=null),this.isEmergencyBrightness&&(this.dispatchEvent(new CustomEvent("emergency-brightness-stop")),this.isEmergencyBrightness=!1),this.isLeftButtonDown=!1}leftButtonLeave(){this.isLeftButtonDown&&(this.leftButtonTimeout&&(clearInterval(this.leftButtonTimeout),this.leftButtonTimeout=null),this.isEmergencyBrightness&&(this.dispatchEvent(new CustomEvent("emergency-brightness-stop")),this.isEmergencyBrightness=!1),this.isLeftButtonDown=!1)}render(){let t=[];this.settings?(t.push(c`<div class="menu-button">
          <obc-icon-button
            variant="flat"
            @pointerdown=${()=>this.leftButtonDown(new CustomEvent("close"))}
            @pointerup=${()=>this.leftButtonUp()}
            @pointerleave=${()=>this.leftButtonLeave()}
          >
            <obi-close-google></obi-close-google>
          </obc-icon-button>
        </div>`),t.push(c`<div class="divider"></div>`),t.push(c`<obc-icon-button
          variant="flat"
          @click=${()=>this.dispatchEvent(new CustomEvent("back"))}
        >
          <obi-arrow-left-google></obi-arrow-left-google>
        </obc-icon-button>`),t.push(c`<div class="title">${this.appTitle}</div>`),t.push(c`<obc-breadcrumb
          .items=${this.breadcrumbItems}
          @breadcrumb-click=${i=>this.dispatchEvent(new CustomEvent("breadcrumb-click",{detail:i.detail}))}
        ></obc-breadcrumb>`)):(this.inactive||t.push(c`<div class="menu-button ${this.wideMenuButton?"wide":null}">
            <obc-icon-button
              variant="flat"
              @pointerdown=${()=>this.leftButtonDown(new CustomEvent("menu-button-clicked"))}
              @pointerup=${()=>this.leftButtonUp()}
              @pointerleave=${()=>this.leftButtonLeave()}
              ?activated=${this.menuButtonActivated}
            >
              ${this.menuButtonIcon==="menu"?c`<obi-menu-iec></obi-menu-iec>`:c`<obi-home></obi-home>`}
            </obc-icon-button>
          </div>`),this.showAppIcon&&t.push(c`<div class="app-icon"><slot name="app-icon"></slot></div>`),t.push(c`<div class="title">${this.appTitle}</div>`),t.push(c`<div class="page-name">${this.pageName}</div>`),t.push(c`<slot name="command-button"></slot>`));let e=Math.max(this.appButtonBreakpointPx,this.dimmingButtonBreakpointPx);return c`
      <style>
                @media (max-width: ${e}px) {
                  .left-more-button {
                    display: revert !important;
        import { customElement } from '../../decorator.js';
                  }

                  .group.left > * {
                    margin-right: 4px;
                    margin-left: 4px;
                  }
                }

                @media (max-width: ${this.appButtonBreakpointPx}px) {
                  .apps-button {
                    display: none;
                  }
                }

                @media (max-width: ${this.dimmingButtonBreakpointPx}px) {
                  .dimming-button {
                    display: none;
                  }
                }

                @media (max-width: ${this.appTitleBreakpointPx}px) {
                  .title {
                    display: none;
                  }
                }

                @media (max-width: ${this.userButtonBreakpointPx}px) {
                  .user-button {
                    display: none;
                  }
                }

                @media (max-width: ${this.appIconBreakpointPx}px) {
                  .app-icon {
                    display: none;
                  }
                }
      </style>
      <nav
        class=${V({wrapper:!0,inactive:this.inactive,settings:this.settings,tall:this.tall})}
        role="menubar"
      >
        <div class="left group">${t}</div>
        <div class="right group">
          <div class="alert-container">
            <slot name="alerts"></slot>
          </div>
          ${this.showDimmingButton&&!this.inactive?c`<obc-icon-button
                class="dimming-button"
                part="dimming-button"
                variant="flat"
                @click=${this.dimmingButtonClicked}
                ?activated=${this.dimmingButtonActivated}
              >
                <obi-palette-day-night-iec></obi-palette-day-night-iec>
              </obc-icon-button>`:null}
          ${this.showUserButton&&!this.inactive?c`<obc-icon-button
                class="user-button"
                variant="flat"
                part="user-button"
                @click=${this.userButtonClicked}
                ?activated=${this.userButtonActivated}
                ?disabled=${this.userButtonDisabled}
              >
                <obi-user></obi-user>
              </obc-icon-button>`:null}
          ${this.showAppsButton&&!this.inactive?c`<obc-icon-button
                class="apps-button"
                variant="flat"
                part="apps-button"
                @click=${this.appsButtonClicked}
                ?activated=${this.appsButtonActivated}
              >
                <obi-applications></obi-applications>
              </obc-icon-button>`:null}
          ${this.showClock?c`<slot name="clock"></slot>`:null}
          ${this.inactive?null:c`<obc-icon-button
                class="left-more-button"
                part="left-more-button"
                variant="flat"
                @click=${this.leftMoreButtonClicked}
                ?activated=${this.leftMoreButtonActivated}
              >
                <obi-more-vertical-google></obi-more-vertical-google>
              </obc-icon-button>`}
        </div>
      </nav>
    `}};T.styles=x(Yo);z([s({type:String})],T.prototype,"appTitle",2);z([s({type:String})],T.prototype,"pageName",2);z([s({type:String})],T.prototype,"menuButtonIcon",2);z([s({type:Boolean})],T.prototype,"menuButtonActivated",2);z([s({type:Boolean})],T.prototype,"dimmingButtonActivated",2);z([s({type:Boolean})],T.prototype,"appsButtonActivated",2);z([s({type:Boolean})],T.prototype,"leftMoreButtonActivated",2);z([s({type:Boolean})],T.prototype,"userButtonActivated",2);z([s({type:Boolean})],T.prototype,"userButtonDisabled",2);z([s({type:Boolean})],T.prototype,"tall",2);z([s({type:Boolean})],T.prototype,"wideMenuButton",2);z([s({type:Boolean})],T.prototype,"showAppsButton",2);z([s({type:Boolean})],T.prototype,"showDimmingButton",2);z([s({type:Boolean})],T.prototype,"showUserButton",2);z([s({type:Boolean})],T.prototype,"showClock",2);z([s({type:Boolean})],T.prototype,"showDate",2);z([s({type:Boolean})],T.prototype,"showAppIcon",2);z([s({type:Boolean})],T.prototype,"inactive",2);z([s({type:Number})],T.prototype,"appButtonBreakpointPx",2);z([s({type:Number})],T.prototype,"dimmingButtonBreakpointPx",2);z([s({type:Number})],T.prototype,"appTitleBreakpointPx",2);z([s({type:Number})],T.prototype,"userButtonBreakpointPx",2);z([s({type:Number})],T.prototype,"appIconBreakpointPx",2);z([s({type:Boolean})],T.prototype,"settings",2);z([s({type:Array})],T.prototype,"breadcrumbItems",2);T=z([h("obc-top-bar")],T);var u1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: block;
  width: 100%;
}

* {
  box-sizing: border-box;
  user-select: none;
}

.wrapper {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  border: 1px solid var(--border-outline-color);
  background: var(--container-background-color);
  height: 100%;
  width: 100%;
  border-radius: var(--ui-components-card-border-radius-regular);
  overflow: hidden;
  anchor-name: --card;
}

.wrapper.has-dialog {
  appearance: none;
  padding: 0;
  margin: 0;
  /* prettier-ignore */
}

.wrapper.has-dialog {
            cursor: pointer;
}

.wrapper.has-dialog:focus {
            outline: none;
}

.wrapper.has-dialog ::after {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.has-dialog.activated ::after {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.has-dialog:hover ::after {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.has-dialog:active ::after {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.has-dialog:focus-visible ::after {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.has-dialog:disabled ::after {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.has-dialog.disabled ::after {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.has-dialog:disabled {
            cursor: not-allowed;
}

.wrapper.has-dialog.disabled {
            cursor: not-allowed;
}

.wrapper.has-dialog {
  box-shadow: var(--shadow-flat);
}

.wrapper.has-dialog::after {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.wrapper.has-dialog:hover::after {
    border-color: var(--flat-hover-border-color);
    background-color: var(--flat-hover-background-color);
  }

.wrapper.has-dialog:active::after {
    border-color: var(--flat-pressed-border-color);
    background-color: var(--flat-pressed-background-color);
  }

.wrapper.has-dialog:focus-visible::after {
    outline-color: var(--border-focus-color);
    outline-width: var(--global-size-spacing-border-weight-focusframe);
    outline-style: solid;
    border-color: var(--container-global-color);
    z-index: 1;
  }

.header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.header .actions {
    display: flex;
    flex-direction: row;
    justify-content: flex-end;
    align-items: center;
  }

.header .title {
    align-self: unset;
  }

.icon {
  width: 24px;
  height: 24px;
  color: var(--element-neutral-color);
}

.title {
  flex-shrink: 0;
  height: var(--ui-components-card-heading-container-height);
  padding: 0 4px;
  gap: 8px;
  font-family: var(--font-family-main);
  font-size: 12px;
  font-style: normal;
  font-weight: var(--global-typography-ui-overline-font-weight);
  line-height: 16px;
  letter-spacing: 1px;
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
  display: flex;
  align-items: center;
  justify-content: center;
}

.content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
}

.dialog-wrapper {
  position: absolute;
  position-anchor: --card;
  left: anchor(left);
  top: anchor(top);
  max-width: 100vw;
  max-height: 100vh;
  position-area: right;
  z-index: 2;
  border-radius: 8px;
  background: var(--container-global-color, #fcfcfc);
  /* Shadow/Floating */
  box-shadow: var(--shadow-floating);
  border-radius: 0;
  overflow: hidden;
  flex-shrink: 0;
  border-radius: 12px;
  padding: 0;
  margin: 0;
  border: 1px solid var(--border-outline-color);
  background: var(--container-background-color);
  box-shadow: var(--shadow-overlay-x) var(--shadow-overlay-y)
    var(--shadow-overlay-blur) var(--shadow-overlay-spread)
    var(--shadow-overlay-color);
}

.dialog-wrapper .header {
    border-bottom: 1px solid var(--border-outline-color);
  }

.dialog-wrapper::backdrop {
  background-color: transparent;
}
`;var Hn=Object.defineProperty,$n=Object.getOwnPropertyDescriptor,Ie=(t,e,i,o)=>{for(var r=o>1?void 0:o?$n(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Hn(e,i,r),r},Le=class extends d{constructor(){super(...arguments),this.showTitle=!0,this.hasDialog=!1,this.dialogTimeOutSeconds=2e4,this.dialogVisibleTimerSeconds=1e4,this.countdownSeconds=0,this.showCountdown=!1}render(){let t=this.hasDialog?R`button`:R`section`;return _`
      <${t} class=${V({wrapper:!0,"has-dialog":this.hasDialog})} @click=${this.openDialog}>
        ${this.showTitle?_`<div class="header">
                <div></div>
                <div class="title">
                  <slot name="title"></slot>
                </div>
                ${this.hasDialog?_`
                      <obi-chevron-right-google
                        class="icon"
                      ></obi-chevron-right-google>
                    `:_`<div></div>`}
              </div>`:f}
        <div class="content">
          <slot></slot>
        </div>
      </${t}>
      ${this.hasDialog?_`
              <dialog class="dialog-wrapper" closedby="any" popover>
                <div class="header">
                  <div></div>
                  <div class="title">
                    <slot name="dialog-title"></slot>
                  </div>
                  <div class="actions">
                    <obc-icon-button
                      @click=${this.closeDialog}
                      variant="flat"
                      .progress=${this.showCountdown?this.getProgressPercentage():void 0}
                    >
                      <obi-close-google></obi-close-google>
                    </obc-icon-button>
                  </div>
                </div>

                <div class="content">
                  <slot name="dialog-content"></slot>
                </div>
              </dialog>
            `:""}
    `}closeDialog(t){t.stopPropagation(),this.clearAllTimers(),this.removeUserActivityListeners(),this.dialog.close()}openDialog(){this.dialog&&(this.dialog.showModal(),this.startDialogTimer(),this.addUserActivityListeners())}startDialogTimer(){this.clearAllTimers();let t=this.dialogTimeOutSeconds-this.dialogVisibleTimerSeconds;this.countdownStartTimer=window.setTimeout(()=>{this.startCountdown()},t),this.dialogTimer=window.setTimeout(()=>{this.dialog.close(),this.clearAllTimers()},this.dialogTimeOutSeconds)}startCountdown(){this.showCountdown=!0;let t=performance.now(),e=this.dialogVisibleTimerSeconds,i=o=>{let r=o-t,a=Math.max(0,e-r);if(this.countdownSeconds=a/1e3,a<=0){this.clearAllTimers();return}this.countdownTimer=requestAnimationFrame(i)};this.countdownTimer=requestAnimationFrame(i)}clearAllTimers(){this.dialogTimer&&(clearTimeout(this.dialogTimer),this.dialogTimer=void 0),this.countdownTimer&&(cancelAnimationFrame(this.countdownTimer),this.countdownTimer=void 0),this.countdownStartTimer&&(clearTimeout(this.countdownStartTimer),this.countdownStartTimer=void 0),this.showCountdown=!1,this.countdownSeconds=0}getProgressPercentage(){let t=this.dialogVisibleTimerSeconds/1e3,e=this.countdownSeconds/t*100;return Math.max(0,e)}addUserActivityListeners(){this.userActivityHandler=()=>{this.resetDialogTimer()},window.addEventListener("mousemove",this.userActivityHandler),window.addEventListener("touchstart",this.userActivityHandler),window.addEventListener("touchmove",this.userActivityHandler),window.addEventListener("keydown",this.userActivityHandler)}removeUserActivityListeners(){this.userActivityHandler&&(window.removeEventListener("mousemove",this.userActivityHandler),window.removeEventListener("touchstart",this.userActivityHandler),window.removeEventListener("touchmove",this.userActivityHandler),window.removeEventListener("keydown",this.userActivityHandler),this.userActivityHandler=void 0)}resetDialogTimer(){this.clearAllTimers(),this.startDialogTimer()}disconnectedCallback(){super.disconnectedCallback(),this.clearAllTimers(),this.removeUserActivityListeners()}};Le.styles=x(u1);Ie([s({type:Boolean,attribute:!1})],Le.prototype,"showTitle",2);Ie([s({type:Boolean})],Le.prototype,"hasDialog",2);Ie([s({type:Number})],Le.prototype,"dialogTimeOutSeconds",2);Ie([s({type:Number})],Le.prototype,"dialogVisibleTimerSeconds",2);Ie([Rt("dialog")],Le.prototype,"dialog",2);Ie([re()],Le.prototype,"countdownSeconds",2);Ie([re()],Le.prototype,"showCountdown",2);Le=Ie([h("obc-card")],Le);var v1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  user-select: none;
}

.wrapper:not(:has(.info)) {
  background: var(--container-background-color);
}

.button {
  overflow: hidden;
  width: 100%;
  height: 100%;
  min-height: var(--ui-components-elevated-card-touch-target-min);
  appearance: none;
  display: flex;
  flex-direction: column;
  justify-content: center;
  text-align: left;
  padding: 0;
  border-width: 0 !important;
  background-color: transparent;
  text-decoration: none;
}

.button.compact {
    min-height: 56px;
  }

.button,
.wrapper {
  border-top-left-radius: var(--elevated-card-border-radius-top-left);
  border-top-right-radius: var(--elevated-card-border-radius-top-right);
  border-bottom-left-radius: var(--elevated-card-border-radius-bottom-left);
  border-bottom-right-radius: var(--elevated-card-border-radius-bottom-right);
}

.center:is(.button,.wrapper),.bottom:is(.button,.wrapper) {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
  }

.center:is(.button,.wrapper),.top:is(.button,.wrapper) {
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }

.button:not(.info) {
  box-shadow: var(--shadow-flat);
}

.button.not-clickable:not(.info) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.button:not(.info):not(.not-clickable) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.button:not(.info):not(.not-clickable):focus {
            outline: none;
}

.button.activated:not(.info):not(.not-clickable) {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.button:not(.info):not(.not-clickable):hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.button:not(.info):not(.not-clickable):active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.button:not(.info):not(.not-clickable):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.button:not(.info):not(.not-clickable):disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.button.disabled:not(.info):not(.not-clickable) {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.top.border.button,
.center.border.button {
  border-bottom: 1px solid var(--border-outline-color) !important;
}

.bottom.border.button {
  border-top: 1px solid var(--border-outline-color) !important;
}

.content-container {
  width: 100%;
  height: 100%;
  display: flex;
  padding: var(--ui-components-elevated-card-padding-vertical)
    var(--ui-components-elevated-card-margin-horizontal);
  align-items: center;
  align-self: stretch;
  background: var(--flat-enabled-background-color);
}

.container-content {
  height: 100%;
  display: flex;
  align-items: baseline;
  flex-grow: 1;
  min-width: 0;
}

.content {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding-right: var(--ui-components-elevated-card-label-spacing);
}

.has-graphic .content-container {
  min-height: var(--ui-components-elevated-card-touch-target-min);
}

.has-leading-icon .leading-icon {
  display: block;
  align-self: center;
  width: calc(
    var(--ui-components-elevated-card-icon-size) +
      var(--ui-components-rich-button-label-spacing)
  );
  height: var(--ui-components-elevated-card-icon-size);
  padding-right: var(--ui-components-rich-button-label-spacing);
  color: var(--element-neutral-color);
  flex-shrink: 0;
  flex-grow: 0;
}

.has-trailing-icon .trailing-icon {
  width: calc(
    var(--ui-components-elevated-card-icon-size) +
      var(--ui-components-rich-button-label-spacing)
  );
  height: var(--ui-components-elevated-card-icon-size);
  padding-left: var(--ui-components-elevated-card-label-spacing);
  color: var(--element-neutral-color);
  flex-shrink: 0;
  flex-grow: 0;
}

::slotted([slot="label"]) {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-active-color);
}

.direct-action ::slotted([slot="label"]) {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-button-font-weight);
  font-size: var(--global-typography-ui-button-font-size);
  line-height: var(--global-typography-ui-button-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-active-color);
}

::slotted([slot="description"]) {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
}

.double-line ::slotted([slot="description"]) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.has-status .status {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
  padding: 0 var(--ui-components-elevated-card-label-spacing);
}

.graphic {
  width: 100%;
}

.graphic-border .graphic {
  border-bottom: 1px solid var(--border-outline-color);
  margin-bottom: -1px;
}

.info .graphic {
  border-radius: var(--ui-components-elevated-card-border-radius)
    var(--ui-components-elevated-card-border-radius) 0 0;
  box-shadow: var(--shadow-flat);
  overflow: hidden;
}
`;var oe=t=>t??f;var m1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.wrapper {
  padding: 0;
  user-select: none;
  background: transparent;
  height: var(--ui-components-button-touch-target-size);
  min-width: var(--ui-components-button-touch-target-size);
  appearance: none;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-feature-settings:
    "liga" off,
    "clig" off;
  font-family: var(--font-family-main);
  font-size: var(--global-typography-ui-button-font-size);
  font-style: normal;
  font-weight: var(--global-typography-ui-button-font-weight);
  line-height: var(--global-typography-ui-button-line-height) /* 150% */;
  text-decoration: none;
}

.wrapper.full-width {
    width: 100%;
  }

.wrapper.full-width .visible-wrapper {
      width: 100%;
    }

.wrapper .visible-wrapper {
    border-radius: var(--ui-components-button-border-radius-top-left)
      var(--ui-components-button-border-radius-top-right)
      var(--ui-components-button-border-radius-bottom-right)
      var(--ui-components-button-border-radius-bottom-left);
    display: flex;
    align-items: center;
    justify-content: center;
    padding-left: calc(2 * var(--ui-components-button-padding-horizontal));
    padding-right: calc(2 * var(--ui-components-button-padding-horizontal));
    height: var(--ui-components-button-visual-size);
  }

.wrapper .icon {
    height: var(--ui-components-button-icon-size);
    width: var(--ui-components-button-icon-size);
  }

.wrapper:not(.hasIconLeading) .icon.leading {
    display: none;
    width: 0;
  }

.wrapper:not(.hasIconTrailing) .icon.trailing {
    display: none;
    width: 0;
  }

.wrapper .label {
    padding-left: var(--ui-components-button-label-spacing);
    padding-right: var(--ui-components-button-label-spacing);
  }

.wrapper.variant-normal {
            cursor: pointer;
}

.wrapper.variant-normal:focus {
            outline: none;
}

.wrapper.variant-normal .visible-wrapper {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper.variant-normal.activated .visible-wrapper {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-normal:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-normal:active .visible-wrapper {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.wrapper.variant-normal:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-normal:disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.variant-normal.disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.variant-normal:disabled {
            cursor: not-allowed;
}

.wrapper.variant-normal.disabled {
            cursor: not-allowed;
}

.wrapper.variant-normal {
    color: var(--on-normal-active-color);
}

.wrapper.variant-normal .icon {
      color: var(--on-normal-neutral-color);
    }

.wrapper.variant-normal:disabled .icon {
      color: var(--on-normal-disabled-color);
    }

.wrapper.variant-flat {
            cursor: pointer;
}

.wrapper.variant-flat:focus {
            outline: none;
}

.wrapper.variant-flat .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.variant-flat.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-flat:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-flat:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.variant-flat:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-flat:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.variant-flat.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.variant-flat:disabled {
            cursor: not-allowed;
}

.wrapper.variant-flat.disabled {
            cursor: not-allowed;
}

.wrapper.variant-flat {
    color: var(--on-flat-active-color);
}

.wrapper.variant-flat .icon {
      color: var(--on-flat-neutral-color);
    }

.wrapper.variant-flat:disabled .icon {
      color: var(--on-flat-disabled-color);
    }

.wrapper.variant-raised {
            cursor: pointer;
}

.wrapper.variant-raised:focus {
            outline: none;
}

.wrapper.variant-raised .visible-wrapper {
            border-color: var(--raised-enabled-border-color);
            background-color: var(--raised-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--raised-enabled-border-color);
            --base-background-color: var(--raised-enabled-background-color);
}

.wrapper.variant-raised.activated .visible-wrapper {
            border-color: var(--raised-activated-border-color);
            background-color: var(--raised-activated-background-color);
            --base-border-color: var(--raised-activated-border-color);
            --base-background-color: var(--raised-activated-background-color);
}

@media (hover:hover) {

.wrapper.variant-raised:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--raised-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--raised-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.variant-raised:active .visible-wrapper {
            border-color: var(--raised-pressed-border-color);
            background-color: var(--raised-pressed-background-color);
}

.wrapper.variant-raised:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.variant-raised:disabled .visible-wrapper {
            border-color: var(--raised-disabled-border-color);
            background-color: var(--raised-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-raised-disabled-color) !important;
}

.wrapper.variant-raised.disabled .visible-wrapper {
            border-color: var(--raised-disabled-border-color);
            background-color: var(--raised-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-raised-disabled-color) !important;
}

.wrapper.variant-raised:disabled {
            cursor: not-allowed;
}

.wrapper.variant-raised.disabled {
            cursor: not-allowed;
}

.wrapper.variant-raised {
    color: var(--on-raised-active-color);
}

.wrapper.variant-raised .icon {
      color: var(--on-raised-neutral-color);
    }

.wrapper.variant-raised:disabled .icon {
      color: var(--on-raised-disabled-color);
    }

.wrapper.segment-position-start {
    margin-right: -1px;
  }

.wrapper.segment-position-start .visible-wrapper {
      border-top-right-radius: 0;
      border-bottom-right-radius: 0;
    }

.wrapper.segment-position-middle .visible-wrapper {
    border-radius: 0;
  }

.wrapper.segment-position-end .visible-wrapper {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
  }

:host:has(.segment-position-start),
:host:has(.segment-position-middle) {
  margin-right: -0.5px;
}

:host:has(.segment-position-middle),
:host:has(.segment-position-end) {
  margin-left: -0.5px;
}
`;var Vn=Object.defineProperty,_n=Object.getOwnPropertyDescriptor,Ae=(t,e,i,o)=>{for(var r=o>1?void 0:o?_n(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Vn(e,i,r),r};var ge=class extends d{constructor(){super(...arguments),this.variant="normal",this.fullWidth=!1,this.disabled=!1,this.showLeadingIcon=!1,this.showTrailingIcon=!1,this.href=void 0,this.target=void 0,this.segmentPosition="single"}renderLeadingIcon(){return this.showLeadingIcon?_`
        <span class="icon leading" part="icon leading">
          <slot name="leading-icon"></slot>
        </span>
      `:_``}renderTrailingIcon(){return this.showTrailingIcon?_`
        <span class="icon trailing" part="icon trailing">
          <slot name="trailing-icon"></slot>
        </span>
      `:_``}render(){let t=this.href?R`a`:R`button`;return _`
      <${t}
        class=${V({wrapper:!0,["variant-"+this.variant]:!0,hasIconLeading:this.showLeadingIcon,hasIconTrailing:this.showTrailingIcon,"full-width":this.fullWidth,["segment-position-"+this.segmentPosition]:!0})}
        ?disabled=${this.disabled}
        href=${oe(this.href)}
        target=${oe(this.target)}
        part="wrapper"
      >
        <div class="visible-wrapper" part="visible-wrapper">
          ${this.renderLeadingIcon()}
          <span class="label" part="label">
            <slot></slot>
          </span>
          ${this.renderTrailingIcon()}
        </div>
      </${t}>
    `}};ge.styles=x(m1);Ae([s({type:String})],ge.prototype,"variant",2);Ae([s({type:Boolean,reflect:!0})],ge.prototype,"fullWidth",2);Ae([s({type:Boolean})],ge.prototype,"disabled",2);Ae([s({type:Boolean})],ge.prototype,"showLeadingIcon",2);Ae([s({type:Boolean})],ge.prototype,"showTrailingIcon",2);Ae([s({type:String})],ge.prototype,"href",2);Ae([s({type:String})],ge.prototype,"target",2);Ae([s({type:String})],ge.prototype,"segmentPosition",2);ge=Ae([h("obc-button")],ge);var Zn=Object.defineProperty,Sn=Object.getOwnPropertyDescriptor,X=(t,e,i,o)=>{for(var r=o>1?void 0:o?Sn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Zn(e,i,r),r};var W=class extends d{constructor(){super(...arguments),this.position="regular",this.size="single-line",this.isClickable=!0,this.info=!1,this.graphicBorder=!1,this.border=!1,this.hasAction=!1,this.hasLeadingIcon=!1,this.hasTrailingIcon=!1,this.hasGraphic=!1,this.hasStatus=!1,this.compact=!1,this.directAction=!1}render(){let t=this.href?R`a`:R`button`;if(t=this.isClickable?t:R`article`,this.overrideTag!==void 0)switch(this.overrideTag){case"a":t=R`a`;break;case"button":t=R`button`;break;case"article":t=R`article`;break;case"div":t=R`div`;break;default:throw new Error("Invalid tag")}return this.hasAction&&(t=R`article`,this.isClickable=!1),_`
    <div class="wrapper ${this.position}">
        <${t} class=${V({button:!0,[this.position]:!0,[this.size]:!0,"graphic-border":this.graphicBorder,info:this.info,border:this.border,"has-leading-icon":this.hasLeadingIcon,"has-trailing-icon":this.hasTrailingIcon,"has-graphic":this.hasGraphic,"has-status":this.hasStatus,"not-clickable":!this.isClickable,"has-action":this.hasAction,compact:this.compact,"direct-action":this.directAction})}
        part="wrapper" href=${oe(this.href)} target=${oe(this.target)}>
          ${this.hasGraphic?_`<div class="graphic"><slot name="graphic"></slot></div>`:f}
          <div class="content-container" part="content-container">
            <div class="container-content">
              ${this.hasLeadingIcon?_`<div class="leading-icon" part="leading-icon">
                      <slot name="leading-icon"></slot>
                    </div>`:f}
              <div class="content" part="label">
                <slot name="label"></slot>
                ${this.size==="single-line"?f:_`<slot name="description"></slot>`}
              </div>
            </div>
            ${this.hasStatus?_`<div class="status" part="status">
                    <slot name="status"></slot>
                  </div>`:f}
            ${this.hasAction?_`<obc-button
                    variant="normal"
                    class="action"
                    part="action"
                    @click=${()=>{this.dispatchEvent(new CustomEvent("action-click"))}}
                  >
                    <slot name="action"></slot>
                  </obc-button>`:f}
            ${this.hasTrailingIcon?_`<div class="trailing-icon" part="trailing-icon">
                    <slot name="trailing-icon"></slot>
                  </div>`:f}
          </div>
        </${t}>
        </div>
    `}};W.styles=x(v1);X([s({type:String})],W.prototype,"position",2);X([s({type:String})],W.prototype,"size",2);X([s({type:String})],W.prototype,"overrideTag",2);X([s({type:Boolean,attribute:!1})],W.prototype,"isClickable",2);X([s({type:Boolean})],W.prototype,"info",2);X([s({type:Boolean})],W.prototype,"graphicBorder",2);X([s({type:Boolean})],W.prototype,"border",2);X([s({type:Boolean})],W.prototype,"hasAction",2);X([s({type:Boolean})],W.prototype,"hasLeadingIcon",2);X([s({type:Boolean})],W.prototype,"hasTrailingIcon",2);X([s({type:Boolean})],W.prototype,"hasGraphic",2);X([s({type:Boolean})],W.prototype,"hasStatus",2);X([s({type:Boolean})],W.prototype,"compact",2);X([s({type:Boolean})],W.prototype,"directAction",2);X([s({type:String})],W.prototype,"href",2);X([s({type:String})],W.prototype,"target",2);W=X([h("obc-elevated-card")],W);var f1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
  user-select: text;
}

.wrapper {
            cursor: pointer;
}

.wrapper:focus {
            outline: none;
}

.wrapper .input-field-container {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper.activated .input-field-container {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.wrapper:hover .input-field-container {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:active .input-field-container {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.wrapper:focus-visible .input-field-container {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:disabled .input-field-container {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.disabled .input-field-container {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper:disabled {
            cursor: not-allowed;
}

.wrapper.disabled {
            cursor: not-allowed;
}

.wrapper {
  display: flex;
  min-height: var(
    --ui-components-input-fields-text-input-field-touch-target-size
  );
  padding: var(--ui-components-input-fields-number-input-field-padding-vertical)
    0;
  align-items: center;
  user-select: none;
  cursor: text;
  position: relative;
  width: 100%;
  /* Override mixin's cursor: pointer on input-field-container */
}

.wrapper .input-field-container {
    cursor: text;
  }

.wrapper.error .input-field-container {
    border: var(--global-size-spacing-border-weight-focusframe) solid
      var(--alert-error-color);
  }

.wrapper.disabled {
    cursor: not-allowed;
  }

.wrapper.disabled .value-input,.wrapper.disabled .unit-text {
      color: var(--on-normal-disabled-color);
      cursor: not-allowed;
    }

.wrapper.helpertext,.wrapper.haslabel {
    flex-direction: column;
    align-items: flex-start;
    flex: 1 0 0;
  }

.wrapper.size-regular .input-field-container {
    height: var(--ui-components-input-fields-number-input-field-visual-size);
  }

.wrapper.size-large .input-field-container {
    height: var(
      --ui-components-input-fields-number-input-field-visual-size-large
    );
  }

.wrapper.error .unit-text {
    color: var(--element-neutral-color);
  }

/* Shared base styles */

.label-text-container {
    display: flex;
    padding: 0
      var(--ui-components-input-fields-number-input-field-label-spacing-title)
      var(--ui-components-input-fields-number-input-field-vertical-spacer);
    align-items: center;
    gap: var(--ui-components-input-fields-text-input-field-required-dot-spacer);
    align-self: stretch;
    user-select: none;
  }

.label-text {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--element-neutral-color);
    user-select: none;
  }

.label-icon {
    width: var(--global-size-spacing-icon-icon-size-small);
    height: var(--global-size-spacing-icon-icon-size-small);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    fill: var(--element-neutral-color);
    color: var(--element-neutral-color);
  }

.label-text-container.label-placement-left {
    justify-content: flex-start;
  }

.label-text-container.label-placement-center {
    justify-content: center;
  }

.label-text-container.label-placement-right {
    justify-content: flex-end;
  }

.required-indicator {
    width: var(--ui-components-input-fields-text-input-field-required-dot-size);
    height: var(
      --ui-components-input-fields-text-input-field-required-dot-size
    );
    border-radius: var(--global-border-radius-border-radius-round);
    background: var(--instrument-enhanced-secondary-color);
  }

.horizontal-container {
    display: flex;
    flex-direction: row;
    align-items: center;
    width: 100%;
    min-width: 0;
  }

.input-field-container {
    display: flex;
    height: var(--ui-components-input-fields-number-input-field-visual-size);
    padding: 0
      var(--ui-components-input-fields-number-input-field-padding-horizontal);
    justify-content: flex-end;
    align-items: center;
    align-self: stretch;
    border-radius: var(
        --ui-components-input-fields-number-input-field-border-radius-top-left
      )
      var(
        --ui-components-input-fields-number-input-field-border-radius-top-right
      )
      var(
        --ui-components-input-fields-number-input-field-border-radius-bottom-right
      )
      var(
        --ui-components-input-fields-number-input-field-border-radius-bottom-left
      );
    border-top: var(
        --ui-components-input-fields-number-input-field-stroke-weight-top
      )
      solid var(--normal-enabled-border-color);
    border-right: var(
        --ui-components-input-fields-number-input-field-stroke-weight-right
      )
      solid var(--normal-enabled-border-color);
    border-bottom: var(
        --ui-components-input-fields-number-input-field-stroke-weight-bottom
      )
      solid var(--normal-enabled-border-color);
    border-left: var(
        --ui-components-input-fields-number-input-field-stroke-weight-left
      )
      solid var(--normal-enabled-border-color);
    background: var(--normal-enabled-background-color);
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
  }

.input-field-container:has(.value-input:focus-visible) {
    outline: var(--global-size-spacing-border-weight-focusframe) solid
      var(--border-focus-color);
    border-color: var(--border-silhouette-color);
    z-index: 1;
  }

.size-regular:scope .input-field-container {
    height: var(--ui-components-input-fields-number-input-field-visual-size);
  }

.size-large:scope .input-field-container {
    height: var(
      --ui-components-input-fields-number-input-field-visual-size-large
    );
  }

.leading-icon {
    width: var(--ui-components-input-fields-text-input-field-icon-size);
    height: var(--ui-components-input-fields-text-input-field-icon-size);
    flex-shrink: 0;
    color: var(--on-normal-neutral-color);
  }

.label-container {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: var(
      --ui-components-input-fields-number-input-field-label-spacing-title
    );
    flex: 1 1 auto;
    min-width: 0;
  }

.value-input {
    font-family: var(--global-typography-font-family);
    font-weight: var(
    --global-typography-instrument-value-regular-font-weight-regular
  );
    font-size: var(--global-typography-instrument-value-regular-font-size);
    line-height: var(--global-typography-instrument-value-regular-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-normal-neutral-color);
    background: transparent;
    border: none;
    outline: none;
    padding: 0 var(--ui-components-input-fields-text-input-field-label-spacing);
    margin: 0;
    min-width: 0;
    width: 100%;
  }

.value-input::placeholder {
    color: var(--element-inactive-color);
  }

.wrapper.disabled .value-input::placeholder {
    color: var(--on-normal-disabled-color);
  }

.helper-text,
  .error-text {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    display: flex;
    padding: var(
        --ui-components-input-fields-number-input-field-vertical-spacer
      )
      var(--ui-components-input-fields-number-input-field-label-spacing-title) 0;
    align-items: center;
    align-self: stretch;
    gap: var(--ui-components-input-fields-text-input-field-required-dot-spacer);
    user-select: none;
  }

.helper-text {
    color: var(--element-neutral-color);
  }

.wrapper.disabled .helper-text {
      color: var(--element-disabled-color);
    }

.error-text {
    color: var(--alert-error-outline-color);
  }

.helper-icon {
    width: var(--global-size-spacing-icon-icon-size-small);
    height: var(--global-size-spacing-icon-icon-size-small);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    fill: var(--element-neutral-color);
    color: var(--element-neutral-color);
  }

.error-text .helper-icon {
    fill: var(--alert-error-outline-color);
    color: var(--alert-error-outline-color);
  }

.helper-text.helper-placement-left,
  .error-text.helper-placement-left {
    justify-content: flex-start;
  }

.helper-text.helper-placement-center,
  .error-text.helper-placement-center {
    justify-content: center;
  }

.helper-text.helper-placement-right,
  .error-text.helper-placement-right {
    justify-content: flex-end;
  }

/* Number input specific: text alignment */

.value-input {
  text-align: right;
}

.squared .input-field-container {
  border-radius: 0;
}

/* Unit */

.unit-text {
  font-family: var(--global-typography-font-family);
  font-weight: var(--global-typography-instrument-unit-font-weight);
  font-size: var(--global-typography-instrument-unit-font-size);
  line-height: var(--global-typography-instrument-unit-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-inactive-color);
  white-space: nowrap;
  height: var(--global-typography-instrument-unit-line-height);
  user-select: none;
}

.unit-text.external {
    padding-left: var(
      --ui-components-input-fields-number-input-field-unit-container-padding-left
    );
  }

.wrapper.align-center .label-container:focus-within .unit-text {
  color: var(--element-neutral-color);
}

/* Alignment variants */

.wrapper.align-center .label-container {
  justify-content: center;
}

.wrapper.align-center .value-input {
  width: auto;
  /* Fallback min-width for empty input - not defined in Figma design tokens */
  min-width: 40px;
  text-align: center;
  flex: 0 0 auto;
}

.wrapper.align-right .label-container,
.wrapper.align-right-unit-outside .label-container {
  justify-content: flex-end;
}
`;var An=Object.defineProperty,Pn=Object.getOwnPropertyDescriptor,O=(t,e,i,o)=>{for(var r=o>1?void 0:o?Pn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&An(e,i,r),r};var S=class extends d{constructor(){super(...arguments),this.value="",this.unit="",this.placeholder="",this.textAlign="right",this.disabled=!1,this.readonly=!1,this.error=!1,this.errorText="",this.rejectUpdatesOnFocus=!1,this.rejectUpdates=!1,this.rejectDuplicateUpdates=!1,this.name="",this.size="regular",this.hasLeadingIcon=!1,this.helperText="",this.label="",this.required=!1,this.hasLabelIcon=!1,this.labelPlacement="left",this.hasHelperIcon=!1,this.helperPlacement="left",this.squared=!1,this.hasFocus=!1,this.previousValue="",this.previousInputElementValue=""}onInput(t){this.value=t.target.value,this.previousInputElementValue=this.value}onFocus(){this.hasFocus=!0}onBlur(){this.hasFocus=!1}get shouldUpdateValue(){return!(this.rejectUpdates||this.rejectUpdatesOnFocus&&this.hasFocus||this.rejectDuplicateUpdates&&this.value===this.previousValue)}willUpdate(t){t.has("value")&&!this.shouldUpdateValue&&this.inputElement&&(this.value=this.inputElement.value)}updated(){this.rejectDuplicateUpdates&&this.value!==this.previousValue&&(this.previousInputElementValue!==this.value||!this.hasFocus)&&(this.previousValue=this.value)}renderFooterText(t,e){return t?c`<div
      id="helper-text"
      class=${V({[e?"error-text":"helper-text"]:!0,[`helper-placement-${this.helperPlacement}`]:!0})}
    >
      ${this.hasHelperIcon?c`<div class="helper-icon"><slot name="helper-icon"></slot></div>`:f}
      ${t}
    </div>`:f}render(){let t=!!this.helperText||!!(this.error&&this.errorText),e=this.unit&&this.textAlign!=="right-unit-outside",i=this.unit&&this.textAlign==="right-unit-outside",o=this.value;return!this.shouldUpdateValue&&this.inputElement&&(o=this.inputElement.value),c`
      <label
        class=${V({wrapper:!0,[`align-${this.textAlign}`]:!0,[`size-${this.size}`]:!0,error:this.error,disabled:this.disabled,helpertext:t,haslabel:!!this.label,squared:this.squared})}
      >
        ${this.label?c`<div
              class=${V({"label-text-container":!0,[`label-placement-${this.labelPlacement}`]:!0})}
            >
              ${this.hasLabelIcon?c`<div class="label-icon">
                    <slot name="label-icon"></slot>
                  </div>`:f}
              <span class="label-text">${this.label}</span>
              ${this.required?c`<div class="required-indicator"></div>`:f}
            </div>`:f}

        <div class="horizontal-container">
          <div class="input-field-container">
            ${this.hasLeadingIcon?c`<div class="leading-icon">
                  <slot name="leading-icon"></slot>
                </div>`:f}
            <div class="label-container">
              <input
                type="text"
                inputmode="decimal"
                class="value-input"
                .value=${o}
                @focus=${this.onFocus}
                @blur=${this.onBlur}
                .placeholder=${this.placeholder}
                name=${oe(this.name||void 0)}
                ?disabled=${this.disabled}
                ?readonly=${this.readonly}
                ?required=${this.required}
                maxlength=${oe(this.maxlength)}
                minlength=${oe(this.minlength)}
                aria-invalid=${this.error?"true":"false"}
                aria-describedby=${oe(t?"helper-text":void 0)}
                autocomplete="off"
                @input=${this.onInput}
              />
              ${e?c`<span class="unit-text">${this.unit}</span>`:f}
            </div>
          </div>
          ${i?c`<span class="unit-text external">${this.unit}</span>`:f}
        </div>

        ${this.error&&this.errorText?this.renderFooterText(this.errorText,!0):this.renderFooterText(this.helperText,!1)}
      </label>
    `}};S.styles=x(f1);O([s({type:String})],S.prototype,"value",2);O([s({type:String})],S.prototype,"unit",2);O([s({type:String})],S.prototype,"placeholder",2);O([s({type:String})],S.prototype,"textAlign",2);O([s({type:Boolean,reflect:!0})],S.prototype,"disabled",2);O([s({type:Boolean,reflect:!0})],S.prototype,"readonly",2);O([s({type:Boolean,reflect:!0})],S.prototype,"error",2);O([s({type:String})],S.prototype,"errorText",2);O([s({type:Boolean})],S.prototype,"rejectUpdatesOnFocus",2);O([s({type:Boolean})],S.prototype,"rejectUpdates",2);O([s({type:Boolean})],S.prototype,"rejectDuplicateUpdates",2);O([s({type:String})],S.prototype,"name",2);O([s({type:Number})],S.prototype,"maxlength",2);O([s({type:Number})],S.prototype,"minlength",2);O([s({type:String})],S.prototype,"size",2);O([s({type:Boolean})],S.prototype,"hasLeadingIcon",2);O([s({type:String})],S.prototype,"helperText",2);O([s({type:String})],S.prototype,"label",2);O([s({type:Boolean})],S.prototype,"required",2);O([s({type:Boolean})],S.prototype,"hasLabelIcon",2);O([s({type:String})],S.prototype,"labelPlacement",2);O([s({type:Boolean})],S.prototype,"hasHelperIcon",2);O([s({type:String})],S.prototype,"helperPlacement",2);O([s({type:Boolean})],S.prototype,"squared",2);O([re()],S.prototype,"hasFocus",2);O([re()],S.prototype,"previousValue",2);O([re()],S.prototype,"previousInputElementValue",2);O([Rt(".value-input")],S.prototype,"inputElement",2);S=O([h("obc-number-input-field")],S);var g1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: block;
}

.wrapper {
  overflow-x: var(--obc-scrollbar-overflow-x, auto);
  overflow-y: auto;
  height: 100%;
  --offset: calc(
    (
        var(--obc-scrollbar-touch-target-size) -
          var(--obc-scrollbar-visual-target-size)
      ) /
      2
  );
}

::-webkit-scrollbar {
  width: var(--obc-scrollbar-touch-target-size);
  height: var(--obc-scrollbar-touch-target-size);
}

/* Transparent-track mode: native scrollbar hidden, custom overlay thumb shown */

.transparent-track {
  scrollbar-width: none;
}

.transparent-track::-webkit-scrollbar {
  display: none;
}

:host {
  position: relative;
}

.overlay-track {
  --_pad: var(--menu-navigation-components-scroll-bar-padding, 4px);
  --_radius: var(--menu-navigation-components-scroll-bar-border-radius, 1000px);

  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: calc(var(--_pad) * 2 + 4px);
  pointer-events: none;
  padding: var(--_pad);
  box-sizing: border-box;
}

.overlay-track::before {
  content: "";
  position: absolute;
  inset: var(--_pad);
  background: var(--border-outline-color, #ddd);
  border-radius: var(--_radius);
}

.overlay-thumb {
  position: absolute;
  left: var(--_pad);
  right: var(--_pad);
  background: var(--element-symbol-color, #8e8e8e);
  border-radius: var(--_radius);
  min-height: 24px;
}

::-webkit-scrollbar-track-piece {
  border: var(--offset) solid transparent;
  border-radius: 9999px;
  background-color: var(--indent-enabled-background-color);
  margin-top: calc(-1 * var(--offset));
  margin-bottom: calc(-1 * var(--offset));
  box-sizing: border-box;
  background-clip: content-box;
}

::-webkit-scrollbar-track-piece:vertical:start {
  border-bottom-width: 0;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
}

::-webkit-scrollbar-track-piece:vertical:end {
  border-top-width: 0;
  border-top-left-radius: 0;
  border-top-right-radius: 0;
}

::-webkit-scrollbar-track-piece:hover {
  outline-color: var(--indent-hover-border-color);
  background-color: var(--indent-hover-background-color);
}

::-webkit-scrollbar-track-piece:active {
  outline-color: var(--indent-pressed-border-color);
  background-color: var(--indent-pressed-background-color);
}

::-webkit-scrollbar-thumb {
  border: calc(var(--offset) + 1px) solid transparent;
  outline: 1px solid var(--obc-scrollbar-thumb-border-color);
  outline-offset: calc(-1 * var(--offset) - 1px);
  background-clip: content-box;
  border-radius: 9999px;
  background-color: var(--obc-scrollbar-thumb-background-color);
  min-height: calc(var(--obc-scrollbar-touch-target-size) * 1.5);
}

::-webkit-scrollbar-thumb:hover {
  outline-color: var(--obc-scrollbar-thumb-hover-border-color);
  background-color: var(--obc-scrollbar-thumb-hover-background-color);
}

::-webkit-scrollbar-thumb:active {
  outline-color: var(--obc-scrollbar-thumb-active-border-color);
  background-color: var(--obc-scrollbar-thumb-active-background-color);
}

::-webkit-scrollbar-button:start:decrement,
::-webkit-scrollbar-button:end:increment {
  display: var(--obc-scrollbar-button-display);
  height: var(--obc-scrollbar-button-size);
  width: var(--obc-scrollbar-button-size);
  box-sizing: border-box;
  background-clip: content-box;
  background-repeat: no-repeat;
  background-position: center;
  border: var(--obc-scrollbar-button-margin) solid transparent;
  border-radius: var(--obc-scrollbar-button-radius);
  background-clip: padding-box;
  background-color: var(--flat-enabled-background-color);
}

::-webkit-scrollbar-button:start:decrement:hover,
::-webkit-scrollbar-button:end:increment:hover {
  background-color: var(--flat-hover-background-color);
}

::-webkit-scrollbar-button:start:decrement:active,
::-webkit-scrollbar-button:end:increment:active {
  background-color: var(--flat-pressed-background-color);
}

::-webkit-scrollbar-button:vertical:start:decrement {
  background-image: var(--icon-02-chevron-up);
}

::-webkit-scrollbar-button:vertical:end:increment {
  background-image: var(--icon-02-chevron-down);
}
`;var On=Object.defineProperty,Bn=Object.getOwnPropertyDescriptor,Ct=(t,e,i,o)=>{for(var r=o>1?void 0:o?Bn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&On(e,i,r),r},Xe=class extends d{constructor(){super(...arguments),this.transparentTrack=!1,this._thumbTop=0,this._thumbHeight=0,this._showOverlayThumb=!1,this._resizeObserver=null,this._scrollHandler=null,this._wrapper=null}render(){return c`
      <div
        class=${V({wrapper:!0,"transparent-track":this.transparentTrack})}
      >
        <slot></slot>
      </div>
      ${this.transparentTrack&&this._showOverlayThumb?c`<div class="overlay-track">
            <div
              class="overlay-thumb"
              style="top:${this._thumbTop}%;height:${this._thumbHeight}%"
            ></div>
          </div>`:f}
    `}firstUpdated(){this._wrapper=this.shadowRoot?.querySelector(".wrapper")??null,this._wrapper&&(this._resizeObserver=new ResizeObserver(()=>{this._checkOverflow(),this._updateOverlayThumb()}),this._resizeObserver.observe(this._wrapper),this._wrapper.querySelector("slot")?.addEventListener("slotchange",()=>{this._checkOverflow(),this._updateOverlayThumb()}),this.transparentTrack&&(this._scrollHandler=()=>this._updateOverlayThumb(),this._wrapper.addEventListener("scroll",this._scrollHandler,{passive:!0})))}disconnectedCallback(){super.disconnectedCallback(),this._resizeObserver?.disconnect(),this._resizeObserver=null,this._scrollHandler&&this._wrapper&&(this._wrapper.removeEventListener("scroll",this._scrollHandler),this._scrollHandler=null),this._wrapper=null}_updateOverlayThumb(){if(!this.transparentTrack||!this._wrapper)return;let{scrollHeight:t,clientHeight:e,scrollTop:i}=this._wrapper;if(t<=e){this._showOverlayThumb=!1;return}this._showOverlayThumb=!0;let o=e,r=parseFloat(getComputedStyle(this._wrapper).getPropertyValue("--menu-navigation-components-scroll-bar-padding"))||4,a=o-r*2,n=e/t*a,v=r+i/t*a;this._thumbTop=v/o*100,this._thumbHeight=n/o*100}_checkOverflow(){if(!this._wrapper)return;let t=this._wrapper.scrollHeight>this._wrapper.clientHeight;this.toggleAttribute("overflowing",t)}scrollToBottom(){if(!this._wrapper)throw new Error("Wrapper not found");this._wrapper.scrollTop=this._wrapper.scrollHeight}};Xe.styles=x(g1);Ct([s({type:Boolean,attribute:"transparent-track"})],Xe.prototype,"transparentTrack",2);Ct([re()],Xe.prototype,"_thumbTop",2);Ct([re()],Xe.prototype,"_thumbHeight",2);Ct([re()],Xe.prototype,"_showOverlayThumb",2);Xe=Ct([h("obc-scrollbar")],Xe);var b1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }
.readout-stack {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  box-sizing: border-box;

  color: var(--element-active-color, #1f1f1f);
}
.readout-stack .icon {
    display: block;
    width: 16px;
    height: 16px;
  }
.readout-stack.small .icon {
    width: 12px;
    height: 12px;
  }
.readout-stack.enhanced .icon {
    width: 24px;
    height: 24px;
  }
.readout-stack .readout-item {
    display: inline-flex;
    padding: 0 4px;
    align-items: center;
    box-sizing: border-box;

    font-family: var(--global-typography-font-family);

    font-weight: var(
    --global-typography-instrument-value-regular-font-weight-regular
  );

    font-size: var(--global-typography-instrument-value-regular-font-size);

    line-height: var(--global-typography-instrument-value-regular-line-height);

    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack .value-container {
    display: flex;
    padding: 0 4px;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    gap: 10px;
    box-sizing: border-box;
  }
.readout-stack .label-container {
    display: flex;
    align-items: baseline;
    gap: var(--Automation-components-readout-item-Enhanced-value-padding, 2px);
    box-sizing: border-box;
  }
.readout-stack .value-text {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 10px;
  }
.readout-stack.small .readout-item {
    font-family: var(--global-typography-font-family);
    font-weight: var(
    --global-typography-instrument-value-small-font-weight-regular
  );
    font-size: var(--global-typography-instrument-value-small-font-size);
    line-height: var(--global-typography-instrument-value-small-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack.enhanced .readout-item {
    font-family: var(--global-typography-font-family);
    font-weight: var(
    --global-typography-instrument-value-large-font-weight-regular
  );
    font-size: var(--global-typography-instrument-value-large-font-size);
    line-height: var(--global-typography-instrument-value-large-line-height);
    letter-spacing: var(
    --global-typography-instrument-value-large-letter-spacing
  );
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack .readout-item.state-off {
    --element-active-color: var(--element-Inactive-color, #707070);
  }
:is(.readout-stack .readout-item.state-off) .value-text {
      font-weight: var(
        --Automation-components-typography-label-font-weight,
        370
      );
    }
.readout-stack .readout-item.state-on {
    /* Styles for state-on type */
  }
.readout-stack obc-button::part(wrapper) {
    /* line-height: var(--global-typography-ui-button-line-height), 24px; */
    line-height: 20px;

    /* height: (--ui-components-button-touch-target-size); 48px, 24px,  */
    height: 20px;
  }
.readout-stack obc-button::part(visible-wrapper) {
    padding-left: 0;
    padding-right: 0;
    height: 20px;
  }
.readout-stack obc-button::part(label) {
    padding-left: 0;
    padding-right: 0;
  }
.readout-stack.small obc-button::part(wrapper) {
    height: 16px;
  }
.readout-stack.small obc-button::part(visible-wrapper) {
    height: 16px;
  }
.readout-stack.enhanced obc-button::part(wrapper) {
    height: 40px;
  }
.readout-stack.enhanced obc-button::part(visible-wrapper) {
    height: 40px;
  }
.readout-stack .value-text {
    color: var(--element-active-color, #1f1f1f);
  }
.label-style-enhanced .readout-stack .value-text {
    color: var(--element-active-color, #1f1f1f);
  }
.readout-stack .unit {
    font-family: var(--font-family-main);
    font-weight: var(--automation-components-typography-unit-regular-font-weight);
    font-size: var(--automation-components-typography-unit-regular-font-size);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    margin-left: 2px;
    padding-right: 2px;
    color: var(--element-neutral-color);
  }
.readout-stack.small .unit {
    font-family: var(--font-family-main);
    font-weight: var(--automation-components-typography-unit-regular-font-weight);
    font-size: var(--automation-components-typography-unit-regular-font-size);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack.enhanced .unit {
    font-family: var(--font-family-main);
    font-weight: var(--automation-components-typography-unit-regular-font-weight);
    font-size: var(--automation-components-typography-unit-regular-font-size);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    position: relative;
  }
.readout-stack .tag {
    display: flex;
    justify-content: center;
    align-items: center;
    align-self: stretch;

    color: var(--element-Inactive-color, #707070);
    font-family: var(--font-family-main);
    font-weight: var(--automation-components-typography-label-font-weight);
    font-size: var(--automation-components-typography-label-font-size);
    line-height: var(--automation-components-typography-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack .tag .hash {
    text-align: center;
    width: 16px;
    margin-right: 4px;
    font-family: var(--font-family-main);
    font-weight: var(--automation-components-typography-label-font-weight);
    font-size: var(--automation-components-typography-label-font-size);
    line-height: var(--automation-components-typography-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }
.readout-stack.small .tag .hash {
    width: 12px;
  }
.readout-stack.enhanced .tag .hash {
    width: 24px;
  }
.label-top .readout-stack,.label-bottom .readout-stack {
    padding-right: 0;
  }
`;var Tn=Object.defineProperty,En=Object.getOwnPropertyDescriptor,C1=(t,e,i,o)=>{for(var r=o>1?void 0:o?En(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Tn(e,i,r),r},Qt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13 20L13 7.83L18.59 13.42L20 12L12 4L4 12L5.41 13.41L11 7.83L11 20L13 20Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13 20L13 7.83L18.59 13.42L20 12L12 4L4 12L5.41 13.41L11 7.83L11 20L13 20Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Qt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;C1([s({type:Boolean})],Qt.prototype,"useCssColor",2);Qt=C1([h("obi-arrow-up-google")],Qt);var zn=Object.defineProperty,Dn=Object.getOwnPropertyDescriptor,y1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Dn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&zn(e,i,r),r},Kt=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11 4L11 16.17L5.41 10.58L4 12L12 20L20 12L18.59 10.59L13 16.17L13 4L11 4Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11 4L11 16.17L5.41 10.58L4 12L12 20L20 12L18.59 10.59L13 16.17L13 4L11 4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Kt.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;y1([s({type:Boolean})],Kt.prototype,"useCssColor",2);Kt=y1([h("obi-arrow-down-google")],Kt);var In=Object.defineProperty,Rn=Object.getOwnPropertyDescriptor,w1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Rn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&In(e,i,r),r},er=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7.11508 18.7051L5.70508 17.2951L11.7051 11.2951L17.7051 17.2951L16.2951 18.7051L11.7051 14.1251L7.11508 18.7051Z" fill="currentColor"/>
<path d="M7.11508 12.7052L5.70508 11.2952L11.7051 5.29517L17.7051 11.2952L16.2951 12.7052L11.7051 8.12517L7.11508 12.7052Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.11508 18.7051L5.70508 17.2951L11.7051 11.2951L17.7051 17.2951L16.2951 18.7051L11.7051 14.1251L7.11508 18.7051Z" style="fill: var(--element-active-color)"/>
<path d="M7.11508 12.7052L5.70508 11.2952L11.7051 5.29517L17.7051 11.2952L16.2951 12.7052L11.7051 8.12517L7.11508 12.7052Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};er.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;w1([s({type:Boolean})],er.prototype,"useCssColor",2);er=w1([h("obi-chevron-double-up-google")],er);var jn=Object.defineProperty,Nn=Object.getOwnPropertyDescriptor,L1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Nn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&jn(e,i,r),r},tr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M16.2948 5.29487L17.7048 6.70487L11.7048 12.7049L5.70483 6.70487L7.11483 5.29487L11.7048 9.87487L16.2948 5.29487Z" fill="currentColor"/>
<path d="M16.2948 11.2948L17.7048 12.7048L11.7048 18.7048L5.70483 12.7048L7.11483 11.2948L11.7048 15.8748L16.2948 11.2948Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M16.2948 5.29487L17.7048 6.70487L11.7048 12.7049L5.70483 6.70487L7.11483 5.29487L11.7048 9.87487L16.2948 5.29487Z" style="fill: var(--element-active-color)"/>
<path d="M16.2948 11.2948L17.7048 12.7048L11.7048 18.7048L5.70483 12.7048L7.11483 11.2948L11.7048 15.8748L16.2948 11.2948Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};tr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;L1([s({type:Boolean})],tr.prototype,"useCssColor",2);tr=L1([h("obi-chevron-double-down-google")],tr);var Fn=Object.defineProperty,Un=Object.getOwnPropertyDescriptor,k1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Un(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Fn(e,i,r),r},rr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M18.41 16.59L17 18L11 12L17 6L18.41 7.41L13.83 12L18.41 16.59Z" fill="currentColor"/>
<path d="M12.41 16.59L11 18L5 12L11 6L12.41 7.41L7.83 12L12.41 16.59Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M18.41 16.59L17 18L11 12L17 6L18.41 7.41L13.83 12L18.41 16.59Z" style="fill: var(--element-active-color)"/>
<path d="M12.41 16.59L11 18L5 12L11 6L12.41 7.41L7.83 12L12.41 16.59Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};rr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;k1([s({type:Boolean})],rr.prototype,"useCssColor",2);rr=k1([h("obi-chevron-double-left-google")],rr);var Wn=Object.defineProperty,Gn=Object.getOwnPropertyDescriptor,M1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Gn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Wn(e,i,r),r},or=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5 7.41L6.41 6L12.41 12L6.41 18L5 16.59L9.58 12L5 7.41Z" fill="currentColor"/>
<path d="M11 7.41L12.41 6L18.41 12L12.41 18L11 16.59L15.58 12L11 7.41Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5 7.41L6.41 6L12.41 12L6.41 18L5 16.59L9.58 12L5 7.41Z" style="fill: var(--element-active-color)"/>
<path d="M11 7.41L12.41 6L18.41 12L12.41 18L11 16.59L15.58 12L11 7.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};or.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;M1([s({type:Boolean})],or.prototype,"useCssColor",2);or=M1([h("obi-chevron-double-right-google")],or);var qn=Object.defineProperty,Xn=Object.getOwnPropertyDescriptor,x1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Xn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&qn(e,i,r),r},ir=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" fill="currentColor"/>
<path d="M8 11C7.44772 11 7 11.4477 7 12C7 12.5523 7.44772 13 8 13H16C16.5523 13 17 12.5523 17 12C17 11.4477 16.5523 11 16 11H8Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" style="fill: var(--element-active-color)"/>
<path d="M8 11C7.44772 11 7 11.4477 7 12C7 12.5523 7.44772 13 8 13H16C16.5523 13 17 12.5523 17 12C17 11.4477 16.5523 11 16 11H8Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ir.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;x1([s({type:Boolean})],ir.prototype,"useCssColor",2);ir=x1([h("obi-off")],ir);var Yn=Object.defineProperty,Jn=Object.getOwnPropertyDescriptor,H1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Jn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Yn(e,i,r),r},ar=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2ZM12 4C16.4183 4 20 7.58172 20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4Z" fill="currentColor"/>
<path d="M12 6C13.1046 6 14 6.89543 14 8L14 16C14 17.1046 13.1046 18 12 18C10.8954 18 10 17.1046 10 16L10 8C10 6.89543 10.8954 6 12 6Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2ZM12 4C16.4183 4 20 7.58172 20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4Z" style="fill: var(--element-active-color)"/>
<path d="M12 6C13.1046 6 14 6.89543 14 8L14 16C14 17.1046 13.1046 18 12 18C10.8954 18 10 17.1046 10 16L10 8C10 6.89543 10.8954 6 12 6Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ar.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;H1([s({type:Boolean})],ar.prototype,"useCssColor",2);ar=H1([h("obi-on")],ar);var Qn=Object.defineProperty,Kn=Object.getOwnPropertyDescriptor,$1=(t,e,i,o)=>{for(var r=o>1?void 0:o?Kn(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Qn(e,i,r),r},nr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 2C13.733 2 15.1492 3.35645 15.2449 5.06546L15.25 5.24987L15.251 13.202L15.331 13.2709C16.2565 14.0975 16.8482 15.2418 16.9746 16.4939L16.9936 16.7457L17 17C17 19.7614 14.7614 22 12 22C9.23858 22 7 19.7614 7 17C7 15.6373 7.5496 14.3655 8.48922 13.4396L8.66993 13.2701L8.749 13.202L8.75 5.25C8.75 3.57886 10.0113 2.20232 11.6339 2.0204L11.8156 2.00514L12 2ZM12 3.5C11.0818 3.5 10.3288 4.20711 10.2558 5.10651L10.25 5.25004L10.2495 13.9445L9.94128 14.1691C9.04185 14.8246 8.5 15.8664 8.5 17C8.5 18.933 10.067 20.5 12 20.5C13.933 20.5 15.5 18.933 15.5 17C15.5 15.9376 15.0241 14.9558 14.2239 14.2971L14.0595 14.1697L13.7515 13.9451L13.75 5.25C13.75 4.2835 12.9665 3.5 12 3.5ZM12 7C12.4142 7 12.75 7.33579 12.75 7.75L12.7506 14.6146C13.7646 14.9334 14.5 15.8808 14.5 17C14.5 18.3807 13.3807 19.5 12 19.5C10.6193 19.5 9.5 18.3807 9.5 17C9.5 15.8804 10.2359 14.9328 11.2504 14.6143L11.25 7.75C11.25 7.33579 11.5858 7 12 7Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 2C13.733 2 15.1492 3.35645 15.2449 5.06546L15.25 5.24987L15.251 13.202L15.331 13.2709C16.2565 14.0975 16.8482 15.2418 16.9746 16.4939L16.9936 16.7457L17 17C17 19.7614 14.7614 22 12 22C9.23858 22 7 19.7614 7 17C7 15.6373 7.5496 14.3655 8.48922 13.4396L8.66993 13.2701L8.749 13.202L8.75 5.25C8.75 3.57886 10.0113 2.20232 11.6339 2.0204L11.8156 2.00514L12 2ZM12 3.5C11.0818 3.5 10.3288 4.20711 10.2558 5.10651L10.25 5.25004L10.2495 13.9445L9.94128 14.1691C9.04185 14.8246 8.5 15.8664 8.5 17C8.5 18.933 10.067 20.5 12 20.5C13.933 20.5 15.5 18.933 15.5 17C15.5 15.9376 15.0241 14.9558 14.2239 14.2971L14.0595 14.1697L13.7515 13.9451L13.75 5.25C13.75 4.2835 12.9665 3.5 12 3.5ZM12 7C12.4142 7 12.75 7.33579 12.75 7.75L12.7506 14.6146C13.7646 14.9334 14.5 15.8808 14.5 17C14.5 18.3807 13.3807 19.5 12 19.5C10.6193 19.5 9.5 18.3807 9.5 17C9.5 15.8804 10.2359 14.9328 11.2504 14.6143L11.25 7.75C11.25 7.33579 11.5858 7 12 7Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};nr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;$1([s({type:Boolean})],nr.prototype,"useCssColor",2);nr=$1([h("obi-temperature-air")],nr);var es=Object.defineProperty,ts=Object.getOwnPropertyDescriptor,at=(t,e,i,o)=>{for(var r=o>1?void 0:o?ts(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&es(e,i,r),r};var Re=class extends d{constructor(){super(...arguments),this.readouts=[],this.tag=null,this.size="regular",this.idTagOrientation="top",this.hasIdTag=!1}renderTag(){if(!this.hasIdTag||!this.tag)return c``;let t=this.tag.value.toString().padStart(4,"0");return c`<div class="tag">#${t}</div>`}renderValueContainer(t,e,i){return c`<div class="readout-item ${t}">
      ${e}
      <div class="value-container">
        <div class="label-container">${i}</div>
      </div>
    </div>`}renderValueText(t){return c`<span class="value-text">${t}</span>`}renderValue(t){let e=t.value.toFixed(0),o=(e.length<t.nDigits?"0".repeat(t.nDigits-e.length):"")+e,r=f;t.icon=="arrow"?t.direction=="up"?r=c`<obi-arrow-up-google
          class="icon"
          useCssColor
        ></obi-arrow-up-google>`:t.direction=="down"?r=c`<obi-arrow-down-google
          class="icon"
          useCssColor
        ></obi-arrow-down-google>`:t.direction=="left"?r=c`<obi-arrow-left-google
          class="icon"
          useCssColor
        ></obi-arrow-left-google>`:t.direction=="right"&&(r=c`<obi-arrow-right-google
          class="icon"
          useCssColor
        ></obi-arrow-right-google>`):t.icon=="chevron"&&(t.direction=="up"?r=c`<obi-chevron-double-up-google
          class="icon"
          useCssColor
        ></obi-chevron-double-up-google>`:t.direction=="down"?r=c`<obi-chevron-double-down-google
          class="icon"
          useCssColor
        ></obi-chevron-double-down-google>`:t.direction=="left"?r=c`<obi-chevron-double-left-google
          class="icon"
          useCssColor
        ></obi-chevron-double-left-google>`:t.direction=="right"&&(r=c`<obi-chevron-double-right-google
          class="icon"
          useCssColor
        ></obi-chevron-double-right-google>`));let a=c`
      ${this.renderValueText(o)}
      <span class="unit">${t.unit}</span>
    `;return this.renderValueContainer("value",r,a)}renderStateOff(t){let e=c``;t.hasIcon&&(e=c`<obi-off class="icon" useCssColor></obi-off>`);let i=this.renderValueText(t.value);return this.renderValueContainer("state-off",e,i)}renderStateOn(t){let e=c``;t.hasIcon&&(e=c`<obi-on class="icon" useCssColor></obi-on>`);let i=this.renderValueText(t.value);return this.renderValueContainer("state-on",e,i)}renderButton(t){let e=t.value.toFixed(1),i=c``;t.hasIcon&&(i=c`<obi-temperature-air
        class="icon"
        useCssColor
      ></obi-temperature-air>`);let o=c`
      ${this.renderValueText(e)}
      <span class="unit">${t.unit}</span>
    `;return c`<obc-button class="readout-button" part="readout-button">
      ${this.renderValueContainer("button",i,o)}
    </obc-button>`}renderReadout(t){if(t.type==="value")return this.renderValue(t);if(t.type==="state-on")return this.renderStateOn(t);if(t.type==="state-off")return this.renderStateOff(t);if(t.type==="button")return this.renderButton(t);throw new Error("Invalid readout type")}render(){let e=this.readouts.filter(r=>r.type==="value"||r.type==="state-off"||r.type==="state-on"||r.type==="button").map(r=>this.renderReadout(r)),i=this.renderTag(),o=[];return this.idTagOrientation==="top"?(this.hasIdTag&&o.push(i),o.push(...e)):(o.push(...e),this.hasIdTag&&o.push(i)),c`<div class="readout-stack ${this.size}">${o}</div>`}};Re.styles=x(b1);at([s({attribute:!1})],Re.prototype,"readouts",2);at([s({attribute:!1})],Re.prototype,"tag",2);at([s()],Re.prototype,"size",2);at([s()],Re.prototype,"idTagOrientation",2);at([s({type:Boolean})],Re.prototype,"hasIdTag",2);Re=at([h("obc-automation-button-readout-stack")],Re);function sr(t,e){return e.strokePosition==="center"?l`<circle id=${t} cx="0" cy="0" 
      r=${e.radius} vector-effect="non-scaling-stroke" 
      stroke=${e.strokeColor}  stroke-width=${e.strokeWidth} 
      fill=${e.fillColor}>`:e.strokePosition==="inside"?l`
		<defs>
			<clipPath id="clip${t}">
				<circle id=${t} cx="0" cy="0" r=${e.radius} vector-effect="non-scaling-stroke" />
			</clipPath>
		</defs>
		<g>
			<circle id=${t} cx="0" cy="0" r=${e.radius} vector-effect="non-scaling-stroke" stroke=${e.strokeColor}  stroke-width=${e.strokeWidth*2} fill=${e.fillColor} clip-path="url(#clip${t})"/>
		</g>
  `:l`
		<circle id=${t} cx="0" cy="0" r=${e.radius} vector-effect="non-scaling-stroke" stroke=${e.strokeColor} stroke-width=${e.strokeWidth*2} fill=${e.fillColor}/>
		  `}var be=(t=>(t.active="active",t.loading="loading",t.off="off",t))(be||{}),D=(t=>(t.regular="regular",t.enhanced="enhanced",t))(D||{});var cr=(t=>(t.notEqual="notEqual",t.equal="equal",t.equalZero="equalZero",t.focus="focus",t))(cr||{});var rs="M22.5918 0.5C25.014 0.50013 26.3186 3.34437 24.917 5.29199L15.0244 19.0371C14.0268 20.423 11.9635 20.423 10.9658 19.0371L1.07326 5.29199C-0.328328 3.34437 0.97623 0.500124 3.39845 0.5L22.5918 0.5Z";var os=13,is=21,as=.8,ns=4,ss=8,lr=300,yt="--setpoint-animation-duration",dr="300ms";function V1(t){let e=getComputedStyle(t).getPropertyValue(yt).trim();if(!e)return lr;let i=parseFloat(e);return Number.isNaN(i)?lr:e.endsWith("s")&&!e.endsWith("ms")?i*1e3:i}function _1(t,e){let i=(e%360+360)%360,o=(t%360+360)%360,r=i-o;return r>180&&(r-=360),r<-180&&(r+=360),t+r}function ls(t,e,i=!1){return i?"var(--instrument-frame-tertiary-color)":t==="focus"?e==="enhanced"?"var(--base-blue-100)":"var(--instrument-regular-tertiary-color)":e==="enhanced"?"var(--instrument-enhanced-primary-color)":"var(--instrument-regular-primary-color)"}function cs(t,e){return t==="focus"?e==="enhanced"?"var(--element-neutral-enhanced-color)":"var(--instrument-regular-secondary-color)":"var(--border-silhouette-color)"}function ds(t){return rs}function ps(t){switch(t){case"equal":case"equalZero":return as;default:return 1}}function mo(t){switch(t){case"equalZero":return ss;case"notEqual":case"focus":return ns;default:return 0}}function fo(t){let{visualState:e,colorMode:i,disabled:o=!1,id:r}=t,a=ls(e,i,o),n=cs(e,i),v=ds(),u=ps(e),m=`${r}-marker`,b=`${r}-mask`,g=-os,C=-is,y=`scale(${u})`;return l`
    <defs>
      <g id="${m}">
        <path
          fill-rule="evenodd"
          clip-rule="evenodd"
          transform="translate(${g}, ${C})"
          d="${v}"
          vector-effect="non-scaling-stroke"
        />
      </g>
      <mask id="${b}">
        <rect x="-20" y="-30" width="50" height="50" fill="white" />
        <use href="#${m}" fill="black" />
      </mask>
    </defs>
    <g transform="${y}" style="transition: transform 200ms ease-in-out;">
      <use href="#${m}" fill="${a}" stroke="none" />
      ${e==="focus"?l`
          <!-- Focus state: 1px silhouette (outer) + 2px colored border (inner) -->
          <!-- First: masked silhouette stroke for outer 1px edge -->
          <use
            href="#${m}"
            mask="url(#${b})"
            fill="none"
            stroke="var(--border-silhouette-color)"
            stroke-width="4"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
          <!-- Second: 2px colored border on top -->
          <use
            href="#${m}"
            fill="none"
            stroke="${n}"
            stroke-width="2"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
        `:l`
          <use
            href="#${m}"
            mask="url(#${b})"
            fill="none"
            stroke="${n}"
            stroke-width="2"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
        `}
    </g>
  `}function Z1(t){let{state:e,priority:i,atSetpoint:o,angleSetpoint:r,setpointAtZeroDeadband:a=.5,newAngleSetpoint:n,touching:v=!1,setpointOverride:u=!1}=t,m=n!==void 0,b=i===D.enhanced?"enhanced":"regular";if(e===be.loading||e===be.off)return{visualState:"notEqual",colorMode:b,disabled:!u,hasNewSetpoint:m};if(v&&!m)return{visualState:"focus",colorMode:b,disabled:!1,hasNewSetpoint:m};let g=r!==void 0&&Math.abs(r)<a;return o&&g?{visualState:"equalZero",colorMode:b,disabled:!1,hasNewSetpoint:m}:o?{visualState:"equal",colorMode:b,disabled:!1,hasNewSetpoint:m}:{visualState:"notEqual",colorMode:b,disabled:!1,hasNewSetpoint:m}}var go=168;function S1(t){let{value:e,setpoint:i,touching:o,auto:r,deadband:a,atSetpointManual:n,angularWraparound:v=!1}=t;if(e===void 0||i===void 0||o)return!1;if(r){let u=Math.abs(e-i);v&&u>180&&(u=360-u);let m=Number.isFinite(a)?a:0;return u<=m}return n}function wt({startAngle:t,endAngle:e,r:i,R:o,roundOutsideCut:r,roundInsideCut:a}){let n=t*Math.PI/180,v=e*Math.PI/180,u=Math.sin(n)*o,m=-Math.cos(n)*o,b=Math.sin(n)*i,g=-Math.cos(n)*i,C=Math.sin(v)*o,y=-Math.cos(v)*o,H=Math.sin(v)*i,E=-Math.cos(v)*i,k=8,w="";if(r){let $=Math.asin(k/o),B=v-$-(n+$)<=Math.PI?0:1,Q=Math.sin(n)*(o-k),F=-Math.cos(n)*(o-k),U=Math.sin(n+$)*o,P=-Math.cos(n+$)*o,I=Math.sin(v)*(o-k),ne=-Math.cos(v)*(o-k),Ve=Math.sin(v-$)*o,rt=-Math.cos(v-$)*o;w+=`M ${Q} ${F} A ${k} ${k} 1 0 1 ${U} ${P}`,w+=`A ${o} ${o} 1 ${B} 1 ${Ve} ${rt}`,w+=`A ${k} ${k} 1 0 1 ${I} ${ne}`}else{let $=Math.abs(v-n)<=Math.PI?0:1;w+=`M ${u} ${m} A ${o} ${o} 1 ${$} 1 ${C} ${y}`}if(a){let $=Math.asin(k/i),B=v-$-(n+$)<=Math.PI?0:1,Q=Math.sin(n)*(i+k),F=-Math.cos(n)*(i+k),U=Math.sin(n+$)*i,P=-Math.cos(n+$)*i,I=Math.sin(v)*(i+k),ne=-Math.cos(v)*(i+k),Ve=Math.sin(v-$)*i,rt=-Math.cos(v-$)*i;w+=`L ${I} ${ne} A ${k} ${k} 1 0 1 ${Ve} ${rt}`,w+=`A ${i} ${i} 1 ${B} 0 ${U} ${P}`,w+=`A ${k} ${k} 1 0 1 ${Q} ${F}`}else{let $=v-n<=Math.PI?0:1;w+=`L ${H} ${E} A ${i} ${i} 1 ${$} 0 ${b} ${g}`}return w+="Z",w}var A1=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.label {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  font-size: calc(12px / var(--scale));
  fill: var(--element-neutral-color);
  dominant-baseline: central;
  text-anchor: middle;
}

.label.left {
    text-anchor: end;
  }

.label.right {
    text-anchor: start;
  }

.label.inside.left {
    text-anchor: start;
  }

.label.inside.right {
    text-anchor: end;
  }
`;var{I:N7}=Go;var P1=t=>t.strings===void 0;var Lt=(t,e)=>{let i=t._$AN;if(i===void 0)return!1;for(let o of i)o._$AO?.(e,!1),Lt(o,e);return!0},pr=t=>{let e,i;do{if((e=t._$AM)===void 0)break;i=e._$AN,i.delete(t),t=e}while(i?.size===0)},O1=t=>{for(let e;e=t._$AM;t=e){let i=e._$AN;if(i===void 0)e._$AN=i=new Set;else if(i.has(t))break;i.add(t),vs(e)}};function hs(t){this._$AN!==void 0?(pr(this),this._$AM=t,O1(this)):this._$AM=t}function us(t,e=!1,i=0){let o=this._$AH,r=this._$AN;if(r!==void 0&&r.size!==0)if(e)if(Array.isArray(o))for(let a=i;a<o.length;a++)Lt(o[a],!1),pr(o[a]);else o!=null&&(Lt(o,!1),pr(o));else Lt(this,t)}var vs=t=>{t.type==it.CHILD&&(t._$AP??=us,t._$AQ??=hs)},hr=class extends De{constructor(){super(...arguments),this._$AN=void 0}_$AT(e,i,o){super._$AT(e,i,o),O1(this),this.isConnected=e._$AU}_$AO(e,i=!0){e!==this.isConnected&&(this.isConnected=e,e?this.reconnected?.():this.disconnected?.()),i&&(Lt(this,e),pr(this))}setValue(e){if(P1(this._$Ct))this._$Ct._$AI(e,this);else{let i=[...this._$Ct._$AH];i[this._$Ci]=e,this._$Ct._$AI(i,this,0)}}disconnected(){}reconnected(){}};var nt=class{constructor(e,{target:i,config:o,callback:r,skipInitial:a}){this.t=new Set,this.o=!1,this.i=!1,this.h=e,i!==null&&this.t.add(i??e),this.l=o,this.o=a??this.o,this.callback=r,window.ResizeObserver?(this.u=new ResizeObserver(n=>{this.handleChanges(n),this.h.requestUpdate()}),e.addController(this)):console.warn("ResizeController error: browser does not support ResizeObserver.")}handleChanges(e){this.value=this.callback?.(e,this.u)}hostConnected(){for(let e of this.t)this.observe(e)}hostDisconnected(){this.disconnect()}async hostUpdated(){!this.o&&this.i&&this.handleChanges([]),this.i=!1}observe(e){this.t.add(e),this.u.observe(e,this.l),this.i=!0,this.h.requestUpdate()}unobserve(e){this.t.delete(e),this.u.unobserve(e)}disconnect(){this.u.disconnect()}target(e){return fs(this,e)}},fs=qe(class extends hr{constructor(){super(...arguments),this.observing=!1}render(t,e){}update(t,[e,i]){this.controller=e,this.part=t,this.observe=i,i===!1?(e.unobserve(t.element),this.observing=!1):this.observing===!1&&(e.observe(t.element),this.observing=!0)}disconnected(){this.controller?.unobserve(this.part.element),this.observing=!1}reconnected(){this.observe!==!1&&this.observing===!1&&(this.controller?.observe(this.part.element),this.observing=!0)}});var ee=(t=>(t.zeroLineThick="zeroLineThick",t.zeroLine="zeroLine",t.main="main",t.primary="primary",t.secondary="secondary",t.tertiary="tertiary",t.textOnly="textOnly",t))(ee||{}),Y=(t=>(t.regular="regular",t.enhanced="enhanced",t))(Y||{});function bo(t,e){return t==="regular"?"var(--instrument-tick-mark-tertiary-color)":e==="tertiary"?"var(--instrument-tick-mark-secondary-color)":"var(--instrument-tick-mark-primary-color)"}function Ye(t,{size:e,style:i,scale:o,text:r,inside:a,textRadius:n,rotation:v,maxDigits:u,color:m,radiusOffset:b=0}){if(o===1/0||o<0)throw new Error("Tick scale is not valid");let g=b,C,y;n=n+(3/o+3)*(a?-1:1);let H=t*Math.PI/180;if(e==="primary")C=328/2+g,y=368/2+g;else if(e==="secondary")C=328/2+g,y=344/2+g;else if(e==="main"||e==="zeroLine")C=320/2+g,y=368/2+g;else if(e==="zeroLineThick")C=224/2+g,y=368/2+g;else if(e==="tertiary")C=328/2+g,y=336/2+g;else return[B1(r??"",t,a,o,n)];if(a){let U=184+g,P=320/2+g,I=y-C,ne=Math.max(0,C-P);y=U-ne,C=y-I}let E=m??bo(i,e),k=Math.sin(H)*C,w=-Math.cos(H)*C,$=Math.sin(H)*y,B=-Math.cos(H)*y,F=l`<line x1=${k} y1=${w} x2=${$} y2=${B} stroke=${E} stroke-width=${e==="zeroLine"||e==="zeroLineThick"?4:1} vector-effect="non-scaling-stroke"/>`;if(r){if(v===void 0)return[F,B1(r,t,a,o,n)];{let U=n+(4/o+5)*(a?-1:1)*u/2,P=Math.sin(H)*U,I=-Math.cos(H)*U;return[F,l`<text x=${P} y=${I} class="label rotate ${a?"inside":""}" transform="rotate(${-v})" transform-origin="${P} ${I}">${r}</text>`]}}return F}function B1(t,e,i,o,r){let a;e===0?a="top":e<180&&e>0?a="right":e===180?a="bottom":a="left";let n=e*Math.PI/180,v=i?-1:1,u=7/o*v,m=6/o*v,b=Math.sin(n)*(r+m);e>180?b+=4/o*v:e<180&&e>0&&(b-=4/o*v);let g=-Math.cos(n)*(r+u);return l`<text x=${b} y=${g} class="label ${a} ${i?"inside":""}">${t}</text>`}var ce=(t=>(t.advice="advice",t.caution="caution",t))(ce||{}),j=(t=>(t.regular="regular",t.hinted="hinted",t.triggered="triggered",t))(j||{}),gs=16/2+8,Co=Math.atan2(gs,672/2);function st(t,e,i,o,r=0){if(((e-t)%360+360)%360*Math.PI/180<=Co*2)return f;let v=t*Math.PI/180+Co,u=e*Math.PI/180-Co,m=328/2+r,b=344/2+r,g=(b-m)/2,C=Math.sin(v)*m,y=-Math.cos(v)*m,H=Math.sin(v)*b,E=-Math.cos(v)*b,k=Math.sin(u)*m,w=-Math.cos(u)*m,$=Math.sin(u)*b,B=-Math.cos(u)*b,Q=`M ${C} ${y} 
                    A ${m} ${m} 0 0 1 ${k} ${w}
                    A ${g} ${g} 0 0 0 ${$} ${B}
                    A ${b} ${b} 0 0 0 ${H} ${E}
                    A ${g} ${g} 0 0 0 ${C} ${y}
                    Z`;return l`<path d=${Q} fill=${i} stroke=${o} stroke-width="1" vector-effect="non-scaling-stroke" />`}function T1(t,e=0){if(t.type==="caution"){let i,o=null;t.state==="hinted"?i="var(--instrument-frame-tertiary-color)":t.state==="regular"?i="var(--instrument-tick-mark-tertiary-color)":(i="var(--on-caution-active-color)",o="var(--alert-caution-color)");let r=[];if(e>0){let C=164+e,y=344/2+e,H=(C+y)/2,E=2*Math.PI*168/90,k=Math.round(2*Math.PI*H/E),w=.705,$=C-12,B=y+12,Q=Math.tan(w)*(B-$)/(2*H);for(let F=0;F<k;F++){let U=F*2*Math.PI/k,P=$*Math.sin(U-Q),I=-$*Math.cos(U-Q),ne=B*Math.sin(U+Q),Ve=-B*Math.cos(U+Q);r.push(l`<line x1=${P} y1=${I} x2=${ne} y2=${Ve} stroke=${i} stroke-width="4"/>`)}}else for(let C=0;C<180;C+=4)r.push(l`<g transform="rotate(${C}) translate(-256 -256) ">
            <path d="M369.167 64.7317L144 194.732L142 191.268L367.167 61.2676L369.167 64.7317ZM369.167 320.732L144 450.732L142 447.267L367.167 317.267L369.167 320.732Z" fill=${i}/>
            </g>
            `);let a=`adviceMask-${t.minAngle}-${t.maxAngle}`,n=Y.regular;t.state==="regular"?n=Y.regular:t.state==="triggered"&&(n=Y.enhanced);let v=e>0?"none":"black",u=st(t.minAngle,t.maxAngle,"white",v,e),m=st(t.minAngle,t.maxAngle,"none",i,e),b,g;if(e>0){let C=172+e+32;b=l`<mask id=${a} maskUnits="userSpaceOnUse" x="${-C}" y="${-C}" width="${C*2}" height="${C*2}">${u}</mask>`,g=o?l`<rect x="${-C}" y="${-C}" width="${C*2}" height="${C*2}" fill="${o}"/>`:f}else b=l`<mask id=${a}>${u}</mask>`,g=o?l`<rect x="-256" y="-256" width="512" height="512" fill="${o}"/>`:f;return l`
            ${b}
            <g mask="url(#${a})">
                ${g}
                ${r}
            </g>
            ${m}
            ${t.hideMinTickmark?f:Ye(t.minAngle,{size:ee.primary,style:n,scale:1,inside:!1,textRadius:0,maxDigits:0,radiusOffset:e})}
            ${t.hideMaxTickmark?f:Ye(t.maxAngle,{size:ee.primary,style:n,scale:1,inside:!1,textRadius:0,maxDigits:0,radiusOffset:e})}
        `}else{let i,o;return t.state==="hinted"?(i="var(--instrument-frame-tertiary-color)",o=Y.regular):t.state==="regular"?(i="var(--instrument-regular-secondary-color)",o=Y.regular):(i="var(--instrument-enhanced-secondary-color)",o=Y.regular),l`
            ${st(t.minAngle,t.maxAngle,t.state==="triggered"?i:"none",i,e)}
            ${Ye(t.minAngle,{size:ee.primary,style:o,scale:1,inside:!1,textRadius:0,maxDigits:0,radiusOffset:e})}
            ${Ye(t.maxAngle,{size:ee.primary,style:o,scale:1,inside:!1,textRadius:0,maxDigits:0,radiusOffset:e})}
        `}}var lt=(t=>(t.dots="dots",t.bar="bar",t))(lt||{}),kt=(t=>(t.scale="scale",t.innerCircle="innerCircle",t))(kt||{}),yo=5,E1=Array.from({length:yo},(t,e)=>360/yo*e),bs=172,Cs=100,de=8,ys=de,ws=de*.75-de*.25,Mt=.05;function xt(t,e=0){return(t==="scale"?bs:Cs)+e}function z1(t,e){let i=t*Math.PI/180;return{cx:Math.sin(i)*e,cy:-Math.cos(i)*e}}function D1(t,e,i=0){let o=xt(e,i);return l`${E1.map(r=>{let{cx:a,cy:n}=z1(r,o);return l`<circle cx="${a}" cy="${n}" r="${ys}" fill="${t}" />`})}`}function Ls(t,e,i){let o=i+de,r=i-de,a=t*Math.PI/180,n=e*Math.PI/180,v=Math.sin(a)*o,u=-Math.cos(a)*o,m=Math.sin(a)*r,b=-Math.cos(a)*r,g=Math.sin(n)*o,C=-Math.cos(n)*o,y=Math.sin(n)*r,H=-Math.cos(n)*r,E=((n-a)%(2*Math.PI)+2*Math.PI)%(2*Math.PI),k,w;return E<=Math.PI?(k=1,w=0):(k=0,w=1),[`M ${v} ${u}`,`A ${o} ${o} 0 0 ${k} ${g} ${C}`,`A ${de} ${de} 0 0 ${k} ${y} ${H}`,`A ${r} ${r} 0 0 ${w} ${m} ${b}`,"Z"].join(" ")}function wo(t,e){let i=((e-t)%360+360)%360;return i<=180?i:360-i}function Lo(t,e=0){let i=xt(t,e);return de/i*(180/Math.PI)}function I1(t,e,i,o=0){let r=xt(i,o),a=de,n=de*2,v=de/2;return l`
    <g transform="rotate(${e})">
      <rect
        x="${-a/2}"
        y="${-r-n/2}"
        width="${a}"
        height="${n}"
        rx="${v}"
        fill="${t}"
      />
    </g>
  `}function R1(t){let{startAngle:e,endAngle:i,barColor:o,position:r,maskId:a="rot-bar-mask",radiusOffset:n=0}=t;if(wo(e,i)<Lo(r,n))return l``;let v=xt(r,n),u=Ls(e,i,v);return l`
    <defs>
      <clipPath id="${a}">
        <path d="${u}" />
      </clipPath>
    </defs>
    <path d="${u}" fill="${o}" />
  `}function j1(t,e,i=0){let o=xt(e,i);return l`
    ${E1.map(r=>{let{cx:a,cy:n}=z1(r,o);return l`<circle cx="${a}" cy="${n}" r="${ws}" fill="${t}" />`})}
  `}var n9=360/yo,s9=de/2;var ur=class{constructor(e,i,o=1,r=0){this._rotationsPerMinute=1,this._cyclePx=0,this.host=e,this.el=i,this._rotationsPerMinute=o,this._cyclePx=r,this.host.addController(this)}set rotationsPerMinute(e){this._rotationsPerMinute!==e&&(this._rotationsPerMinute=e,this.updateAnimation())}get rotationsPerMinute(){return this._rotationsPerMinute}set cyclePx(e){this._cyclePx!==e&&(this._cyclePx=e,this.updateAnimation())}get cyclePx(){return this._cyclePx}get isTranslateMode(){return this._cyclePx>0}getKeyframes(){return this.isTranslateMode?[{transform:"translateX(0px)"},{transform:`translateX(${this._cyclePx}px)`}]:[{transform:"rotate(0deg)"},{transform:"rotate(360deg)"}]}hostConnected(){this.startAnimation()}startAnimation(){let e=Math.abs(this._rotationsPerMinute),i=e===0?1:1e3*60/e;this.animation=this.el.animate(this.getKeyframes(),{duration:i,iterations:1/0,direction:this._rotationsPerMinute>=0?"normal":"reverse"}),this._rotationsPerMinute===0&&this.animation.pause()}updateAnimation(){if(!this.animation)return;let e=this.animation.effect.getComputedTiming(),i=e.duration,o=this.animation.currentTime??0,r=e.direction,a=o%i/i;this.animation.cancel();let n=Math.abs(this._rotationsPerMinute),v=n===0?1:1e3*60/n,u=this._rotationsPerMinute>=0?"normal":"reverse",m=r!==u?1-a:a;this.animation=this.el.animate(this.getKeyframes(),{duration:v,iterations:1/0,direction:u}),this.animation.currentTime=m*v,this._rotationsPerMinute===0&&this.animation.pause()}destroy(){this.animation?.cancel(),this.animation=void 0}hostDisconnected(){this.destroy()}};function vr(t,e){e&&(e.destroy(),t.removeController(e))}function ko(t){let{scale:e,inside:i,innerRadius:o,includeNorth:r}=t,a=16,n=8,v=368/2,u=g=>g*(i?o-n/e-a/2:v+n/e+a/2),m=[{label:"E",x:u(1),y:0},{label:"S",x:0,y:u(1)},{label:"W",x:u(-1),y:0}],b=e<.58;return(r||b||i)&&m.push({label:"N",x:0,y:u(-1)}),m}function N1(t,e){let i,o,r,a,n;typeof t=="number"?(i=t,o=e,r=!1,a=368/2):(i=t.scale,o=t.rotation,r=t.inside??!1,a=t.innerRadius??368/2,n=t.includeNorth);let v=ko({scale:i,inside:r,innerRadius:a,includeNorth:n});return l`
    ${v.map(u=>l`
        <text
          x="${u.x}"
          y="${u.y}"
          class="label"
          transform="rotate(${-(o??0)})"
          transform-origin="${u.x} ${u.y}"
        >
          ${u.label}
        </text>
      `)}
  `}function F1(t){let{scale:e,rotation:i,inside:o=!1}=t,r=368/2;return e<.58?o?l`
        <g transform="translate(0, ${-r})">
          <path fill-rule="evenodd" clip-rule="evenodd"
            d="M-17.8457 24.984 0 0 17.8458 24.984C11.9868 24.3338 6.0324 24 0 24-6.0323 24-11.9867 24.3338-17.8457 24.984Z"
            fill="var(--instrument-frame-tertiary-color)"/>
        </g>`:l`
        <defs>
          <mask id="circleMask">
            <rect x="-${r}" y="-${r}" width="${r*2}" height="${r*2}" fill="black"/>
            <circle cx="0" cy="0" r="${r}" fill="white"/>
          </mask>
        </defs>
        <g mask="url(#circleMask)" transform="translate(0, ${-r})">
          <path fill-rule="evenodd" clip-rule="evenodd"
            d="M-17.8457 24.984 0 0 17.8458 24.984C11.9868 24.3338 6.0324 24 0 24-6.0323 24-11.9867 24.3338-17.8457 24.984Z"
            fill="var(--instrument-frame-tertiary-color)"/>
        </g>`:o?l`
      <path transform="translate(-256, -256)" fill-rule="evenodd" clip-rule="evenodd"
        d="M238.152 96.9842L255.998 72L273.844 96.9839C267.985 96.3338 262.031 96 256 96C249.967 96 244.012 96.3339 238.152 96.9842Z"
        fill="var(--instrument-frame-tertiary-color)"/>
    `:l`
    <g transform="translate(0, ${(1/e-1)*188}) scale(${1/e})">
      <path transform="translate(-192, -224)"
        d="M 221.521 35.425 C 222.388 36.4644 222.821 36.9841 222.809 37.3627 C 222.8 37.6941 222.632 37.9916 222.354 38.1721 C 222.037 38.3783 221.361 38.2774 220.011 38.0756 A ${188*e} ${188*e} 0 0 0 163.989 38.0756 C 162.639 38.2774 161.964 38.3783 161.646 38.1721 C 161.368 37.9916 161.201 37.6941 161.191 37.3627 C 161.18 36.9841 161.613 36.4644 162.479 35.425 L 190.771 1.475 C 191.193 0.9685 191.404 0.7153 191.657 0.6229 C 191.879 0.5419 192.122 0.5419 192.343 0.6229 C 192.596 0.7153 192.807 0.9685 193.229 1.475 L 221.521 35.425 Z"
        fill="var(--instrument-tick-mark-secondary-color)"/>
    </g>

    <defs>
      <mask id="circleMask">
        <rect x="-${r}" y="-${r}" width="${r*2}" height="${r*2}" fill="black"/>
        <circle cx="0" cy="0" r="${r}" fill="white"/>
      </mask>
    </defs>
    <g mask="url(#circleMask)" transform="translate(0, ${-(r+10/e+30)}) scale(${.75/e}, ${.75/e}) rotate(${-(i??0)})" transform-origin="0 25">
      <path d="M5.003 29H2.091L-3.013 20.264H-3.077C-3.066 20.52-3.056 20.7813-3.045 21.048-3.034 21.3147-3.024 21.5867-3.013 21.864-2.992 22.1307-2.976 22.4027-2.965 22.68-2.954 22.9573-2.944 23.2347-2.933 23.512V29H-4.997V17.576H-2.101L2.987 26.232H3.035C3.024 25.9867 3.014 25.736 3.003 25.48 2.992 25.2133 2.982 24.952 2.971 24.696 2.971 24.4293 2.966 24.1627 2.955 23.896 2.944 23.6293 2.934 23.3627 2.923 23.096V17.576H5.003V29Z" fill="var(--element-active-inverted-color)"/>
    </g>
  `}var U1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M92 66.6364H83.7941L83.1324 65.4385L84.2794 62.1943H85.2941L82.4265 60.9964H82.0735L81.8057 59.7842C81.7044 59.3261 81.2984 59 80.8292 59H79.1708C78.7016 59 78.2956 59.3261 78.1943 59.7842L77.9265 60.9964H77.5735L74.7059 62.1943H75.7206L76.8676 65.4385L76.2059 66.6364H68V67.0856H69.3235V70.2299H68V79.3137V80.0624L68.5089 82.024C68.9278 83.639 70.1096 84.8535 71.5707 85.1706L80 87L88.4293 85.1706C89.8904 84.8535 91.0722 83.639 91.4911 82.024L92 80.0624V79.3137V70.2299V66.6364ZM86.3529 71.9657V79.3137H70.081V71.9657H86.3529Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92 80.0624L91.4911 82.024C91.0722 83.639 89.8904 84.8535 88.4293 85.1706L80 87L71.5707 85.1706C70.1096 84.8535 68.9278 83.639 68.5089 82.024L68 80.0624M92 80.0624H68M92 80.0624V79.3137M83.7941 66.6364H92V70.2299M83.7941 66.6364L83.1324 65.4385M83.7941 66.6364H76.2059M83.1324 65.4385L84.2794 62.1943M83.1324 65.4385H76.8676M84.2794 62.1943H85.2941L82.4265 60.9964H82.0735M84.2794 62.1943H75.7206M68 80.0624V79.3137M76.2059 66.6364H68V67.0856H69.3235V70.2299M76.2059 66.6364L76.8676 65.4385M76.8676 65.4385L75.7206 62.1943M75.7206 62.1943H74.7059L77.5735 60.9964H77.9265M68 79.3137H70.081M68 79.3137V70.2299H69.3235M92 79.3137H86.3529M92 79.3137V70.2299M86.3529 79.3137V71.9657H70.081V79.3137M86.3529 79.3137H70.081M69.3235 70.2299H92M82.0735 60.9964H81.7206H78.2794H77.9265M82.0735 60.9964L81.8057 59.7842C81.7044 59.3261 81.2984 59 80.8292 59H79.1708C78.7016 59 78.2956 59.3261 78.1943 59.7842L77.9265 60.9964" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var W1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 74.9115L13.0001 73.5L48.0001 73L52.8784 68.1352H75.4774L76.1648 65.6631L75.0908 62.3099H74.3605L76.6374 60H83.3628L85.6396 62.3099H84.9093L83.8353 65.6631L84.5227 68.1352H107.122L112 73L147 73.5L150 74.9115L150 80.16L147 81.8885L146.846 83.4086C146.791 83.95 146.452 84.3687 146.031 84.4377C145.96 84.4493 145.89 84.4476 145.818 84.4479C144.806 84.451 136.713 84.4895 128.544 84.9172C124.018 85.1541 118.577 85.6275 113.488 86.1336C102.356 87.2408 91.1872 88 80.0001 88C68.813 88 57.6441 87.2408 46.5119 86.1336C41.4228 85.6275 35.9817 85.1541 31.456 84.9172C23.2869 84.4895 15.194 84.451 14.182 84.4479C14.1104 84.4476 14.0397 84.4493 13.969 84.4377C13.5479 84.3687 13.2092 83.95 13.1543 83.4086L13.0001 81.8885L10.0001 80.16L10 74.9115Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M48.0001 73L13.0001 73.5L10 74.9115L10.0001 80.16M48.0001 73L52.8784 68.1352H75.4774M48.0001 73H112M75.4774 68.1352L76.1648 65.6631M75.4774 68.1352H84.5227M76.1648 65.6631L75.0908 62.3099M76.1648 65.6631H83.8353M75.0908 62.3099H74.3605L76.6374 60H83.3628L85.6396 62.3099H84.9093M75.0908 62.3099H84.9093M10.0001 80.16L13.0001 81.8885L13.1543 83.4086C13.2092 83.95 13.5479 84.3687 13.969 84.4377C14.0397 84.4493 14.1104 84.4476 14.182 84.4479C15.194 84.451 23.2869 84.4895 31.456 84.9172C35.9817 85.1541 41.4228 85.6275 46.5119 86.1336C57.6441 87.2408 68.813 88 80.0001 88C91.1872 88 102.356 87.2408 113.488 86.1336C118.577 85.6275 124.018 85.1541 128.544 84.9172C136.713 84.4895 144.806 84.451 145.818 84.4479C145.89 84.4476 145.96 84.4493 146.031 84.4377C146.452 84.3687 146.791 83.95 146.846 83.4086L147 81.8885L150 80.16M10.0001 80.16H150M112 73L147 73.5L150 74.9115L150 80.16M112 73L107.122 68.1352H84.5227M84.5227 68.1352L83.8353 65.6631M83.8353 65.6631L84.9093 62.3099" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var G1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80.0007 151.999C73.373 152 68 146.627 68 139.999L68 128.776L68 104.642L68 56.7557L68 19.9992C68 13.3717 73.3726 7.99916 80 7.99916C86.6274 7.99916 92 13.3717 92 19.9992L92 23.108L92 56.7557L92 108.092L92 137.357L92 139.999C92 146.626 86.6278 151.999 80.0007 151.999Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8387 85.9422L73.9677 85.9422L73.9677 74.336L85.8387 74.336L85.8387 85.9422Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92 108.092L86.2419 108.092M92 108.092L92 56.7557M92 108.092L92 137.357M86.2419 108.092L84.4516 104.642L72.9355 104.642L68 104.642M86.2419 108.092L86.2419 137.357L92 137.357M68 104.642L68 128.776L68 139.999C68 146.627 73.373 152 80.0007 151.999V151.999C86.6278 151.999 92 146.626 92 139.999L92 137.357M68 104.642L68 56.7557M68 56.7557L68 19.9992C68 13.3717 73.3726 7.99916 80 7.99916V7.99916V7.99916C86.6274 7.99916 92 13.3717 92 19.9992L92 23.108M68 56.7557L86.2419 56.7557M92 56.7557L86.2419 56.7557M92 56.7557L92 23.108M86.2419 56.7557L86.2419 23.108L92 23.108M73.9677 85.9422L85.8387 85.9422M73.9677 85.9422L73.9677 74.336M73.9677 85.9422L76.5806 83.424M85.8387 85.9422L85.8387 74.336M85.8387 85.9422L83.2258 83.424M85.8387 74.336L73.9677 74.336M85.8387 74.336L83.2258 76.8541M73.9677 74.336L76.5806 76.8541M76.5806 83.424L83.2258 83.424M76.5806 83.424L76.5806 76.8541M83.2258 83.424L83.2258 76.8541M83.2258 76.8541L76.5806 76.8541" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var q1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="60" y="52" width="40" height="3" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M80.0036 77.9545V87C80.0036 87 83.7476 81.9921 82.7622 80C82.1928 78.8489 80.0036 77.9545 80.0036 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87V77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545C77.2603 79.9697 77.2525 79.9848 77.245 80C76.2596 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80H82.7622C83.7476 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545H65.2344Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M69 64H65.2344V74V79.9545H77.2684C77.8718 78.8255 80.0036 77.9545 80.0036 77.9545L80.0036 64H69Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7728 64H91H80.0036L80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80H94.7728V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 64V52H69V64H80.0036H91Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 52L94 49H66L69 52H91Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66 49H94H94.7728L93 47.2273H83.0301H81.184H78.8232H76.9771H67.133L65.2344 49H66Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.0301 39H77.0036L76.9771 47.2273H78.8232L78.7728 40.4205H81.2344L81.184 47.2273H83.0301V39Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 64H94.7728V74V79.9545V80M91 64V52M91 64H80.0036M91 52L94 49M91 52H69M94 49H66M94 49H94.7728L93 47.2273H83.0301M66 49L69 52M66 49H65.2344L67.133 47.2273H76.9771M69 52V64M69 64H65.2344V74V79.9545M69 64H80.0036M76.9771 47.2273H83.0301M76.9771 47.2273L77.0036 39H83.0301V47.2273M76.9771 47.2273H78.8232M83.0301 47.2273H81.184M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036M65.2344 79.9545H77.2684M78.8232 47.2273L78.7728 40.4205H81.2344L81.184 47.2273M78.8232 47.2273H81.184M80.0036 64L80.0036 77.9545M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80M80.0036 87V77.9545M80.0036 87C80.0036 87 83.7476 81.9921 82.7622 80M80.0036 87C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545M80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80M80.0036 77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545M82.7622 80H94.7728" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M80.0036 77.9545V87C80.0036 87 83.7476 81.9921 82.7622 80C82.1928 78.8489 80.0036 77.9545 80.0036 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87V77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545C77.2603 79.9697 77.2525 79.9848 77.245 80C76.2596 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80H82.7622C83.7476 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545H65.2344Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7728 64H92.3113H80.0036L80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80H94.7728V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036M65.2344 79.9545V74V64H67.6959H80.0036M65.2344 79.9545H77.2684M80.0036 64H92.3113H94.7728V74V79.9545V80M80.0036 64L80.0036 77.9545M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80M80.0036 87V77.9545M80.0036 87C80.0036 87 83.7476 81.9921 82.7622 80M80.0036 87C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545M80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80M80.0036 77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545M82.7622 80H94.7728" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="87.498" cy="70.0003" rx="1.5" ry="2" transform="rotate(45 87.498 70.0003)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="72.4983" cy="70" rx="1.5" ry="2" transform="rotate(-45 72.4983 70)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M96 55L91 60" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M64 55L69 60" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var X1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71H18.4844V63L22 44H26V63H32.4844V53.5604V50.1099L31 48.9973L32 48.1429H37.4294L37.2747 38.5H39.5L41.88 48.1429H45.8152C48.7962 48.1429 51.7388 48.8152 54.4239 50.1099H52.5695L50.3443 53.5604V71H117.416L124.833 64.1236H148C148 64.1236 146.5 67 144.5 71C143.302 73.3966 143.5 75.6209 143.5 75.6209C145.701 75.6209 147.484 77.4047 147.484 79.6053V80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71H18.4844M147.484 80V79.6053C147.484 77.4047 145.701 75.6209 143.5 75.6209V75.6209C143.5 75.6209 143.302 73.3966 144.5 71C146.5 67 148 64.1236 148 64.1236H124.833L117.416 71H50.3443M18.4844 71H50.3443M18.4844 71V63L22 44H26V63H32.4844V53.5604M32.4844 53.5604H50.3443M32.4844 53.5604V50.1099M50.3443 53.5604L52.5695 50.1099H32.4844M50.3443 53.5604V71M32.4844 50.1099H54.4239V50.1099C51.7388 48.8152 48.7962 48.1429 45.8152 48.1429H41.88M32.4844 50.1099L31 48.9973L32 48.1429H37.4294M41.88 48.1429L39.5 38.5H37.2747L37.4294 48.1429M41.88 48.1429H37.4294" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="136" cy="70" r="2" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Y1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 122L64 122L64 118L72 118L75 114L85 114L88 118L96 118L96 122L86 122L86 138.75L74 138.75L74 122Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var J1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80 77.9545V87C80 87 83.744 81.9921 82.7586 80C82.1892 78.8489 80 77.9545 80 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 87V77.9545C80 77.9545 77.8682 78.8255 77.2648 79.9545C77.2567 79.9697 77.2489 79.9848 77.2414 80C76.256 81.9921 80 87 80 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 87H90.7692C92.9784 87 94.7692 85.2091 94.7692 83V80H82.7586C83.744 81.9921 80 87 80 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2308 79.9545V83C65.2308 85.2091 67.0216 87 69.2308 87H80C80 87 76.256 81.9921 77.2414 80C77.2489 79.9848 77.2567 79.9697 77.2648 79.9545H65.2308Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.6923 64H65.2308V74V79.9545H77.2648C77.8682 78.8255 80 77.9545 80 77.9545L80 64H67.6923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7692 64H92.3077H80L80 77.9545C80 77.9545 82.1892 78.8489 82.7586 80H94.7692V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 64V57.75H67.6923V64H80H92.3077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 57.75L94.7692 52.6364H65.2308L67.6923 57.75H92.3077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2308 52.6364H94.7692H96L92.3077 49.2273H83.0265H81.1804H78.8196H76.9735H67.6923L64 52.6364H65.2308Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.0265 41H77L76.9735 49.2273H78.8196L78.7692 42.4205H81.2308L81.1804 49.2273H83.0265V41Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 64H94.7692V74V79.9545V80M92.3077 64V57.75M92.3077 64H80M92.3077 57.75L94.7692 52.6364M92.3077 57.75H67.6923M94.7692 52.6364H65.2308M94.7692 52.6364H96L92.3077 49.2273H83.0265M65.2308 52.6364L67.6923 57.75M65.2308 52.6364H64L67.6923 49.2273H76.9735M67.6923 57.75V64M67.6923 64H65.2308V74V79.9545M67.6923 64H80M76.9735 49.2273H83.0265M76.9735 49.2273L77 41H83.0265V49.2273M76.9735 49.2273H78.8196M83.0265 49.2273H81.1804M65.2308 79.9545V83C65.2308 85.2091 67.0216 87 69.2308 87H80M65.2308 79.9545H77.2648M78.8196 49.2273L78.7692 42.4205H81.2308L81.1804 49.2273M78.8196 49.2273H81.1804M80 64L80 77.9545M80 87H90.7692C92.9784 87 94.7692 85.2091 94.7692 83V80M80 87V77.9545M80 87C80 87 83.744 81.9921 82.7586 80M80 87C80 87 76.256 81.9921 77.2414 80C77.2489 79.9848 77.2567 79.9697 77.2648 79.9545M80 77.9545C80 77.9545 82.1892 78.8489 82.7586 80M80 77.9545C80 77.9545 77.8682 78.8255 77.2648 79.9545M82.7586 80H94.7692M75.5862 72L75.0345 71H71.7241L72.2759 72H75.5862ZM83.8621 72L84.4138 71H87.7241L87.1724 72H83.8621Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M79.4545 70V65.7333H74V64.1818H74.5455V55.6485V38.1939V19.1879V7.16364H74V6H86V7.16364V64.1818V65.7333H84.0909V70H79.4545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.5455 64.1818H74V65.7333H79.4545V70H84.0909V65.7333H86V64.1818M74.5455 64.1818H86M74.5455 64.1818V55.6485M74.5455 7.16364H74V6H86V7.16364M74.5455 7.16364H86M74.5455 7.16364V19.1879M86 64.1818V7.16364M74.5455 19.1879H81.9091M74.5455 19.1879V38.1939M74.5455 38.1939H81.9091M74.5455 38.1939V55.6485M74.5455 55.6485H81.9091" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M80.0036 77.9545V87C80.0036 87 83.7476 81.9921 82.7622 80C82.1928 78.8489 80.0036 77.9545 80.0036 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87V77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545C77.2603 79.9697 77.2525 79.9848 77.245 80C76.2596 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80H82.7622C83.7476 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545H65.2344Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.6959 64H65.2344V74V79.9545H77.2684C77.8718 78.8255 80.0036 77.9545 80.0036 77.9545L80.0036 64H67.6959Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7728 64H92.3113H80.0036L80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80H94.7728V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036M65.2344 79.9545V74V64H67.6959H80.0036M65.2344 79.9545H77.2684M80.0036 64H92.3113H94.7728V74V79.9545V80M80.0036 64L80.0036 77.9545M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80M80.0036 87V77.9545M80.0036 87C80.0036 87 83.7476 81.9921 82.7622 80M80.0036 87C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545M80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80M80.0036 77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545M82.7622 80H94.7728M75.5898 72L75.0381 71H71.7277L72.2795 72H75.5898ZM83.8657 72L84.4174 71H87.7277L87.176 72H83.8657Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Q1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M119.273 71V66.7333H112V65.1818H112.727V56.6485V39.1939V20.1879V8.16364H112V7H128V8.16364V65.1818V66.7333H125.455V71H119.273Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M112.727 65.1818H112V66.7333H119.273V71H125.455V66.7333H128V65.1818M112.727 65.1818H128M112.727 65.1818V56.6485M112.727 8.16364H112V7H128V8.16364M112.727 8.16364H128M112.727 8.16364V20.1879M128 65.1818V8.16364M112.727 20.1879H122.545M112.727 20.1879V39.1939M112.727 39.1939H122.545M112.727 39.1939V56.6485M112.727 56.6485H122.545" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71V58.5604V54.1099L11 52.9973L12 51.1429H17.4294L17.2747 41.5H19.5L21.88 51.1429H25.2998C28.5783 51.1429 31.7725 52.1816 34.4239 54.1099H32.5695L30.3443 58.5604V71H117.416L124.833 64.1236H146.743C146.743 64.1236 143.808 67.7438 142.292 70.614C141.041 72.9834 139.325 77.1044 139.325 77.1044L143.176 76.4042C145.419 75.9963 147.484 77.7198 147.484 80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71M147.484 80V80C147.484 77.7198 145.419 75.9963 143.176 76.4042L139.325 77.1044C139.325 77.1044 141.041 72.9834 142.292 70.614C143.808 67.7438 146.743 64.1236 146.743 64.1236H124.833L117.416 71H30.3443M12.4844 71V58.5604M12.4844 71H30.3443M12.4844 58.5604H30.3443M12.4844 58.5604V54.1099M30.3443 58.5604L32.5695 54.1099H12.4844M30.3443 58.5604V71M12.4844 54.1099H34.4239V54.1099C31.7725 52.1816 28.5783 51.1429 25.2998 51.1429H21.88M12.4844 54.1099L11 52.9973L12 51.1429H17.4294M21.88 51.1429L19.5 41.5H17.2747L17.4294 51.1429M21.88 51.1429H17.4294" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M95.2727 71V66.7333H88V65.1818H88.7273V56.6485V39.1939V20.1879V8.16364H88V7H104V8.16364V65.1818V66.7333H101.455V71H95.2727Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M88.7273 65.1818H88V66.7333H95.2727V71H101.455V66.7333H104V65.1818M88.7273 65.1818H104M88.7273 65.1818V56.6485M88.7273 8.16364H88V7H104V8.16364M88.7273 8.16364H104M88.7273 8.16364V20.1879M104 65.1818V8.16364M88.7273 20.1879H98.5455M88.7273 20.1879V39.1939M88.7273 39.1939H98.5455M88.7273 39.1939V56.6485M88.7273 56.6485H98.5455" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71.2727 71V66.7333H64V65.1818H64.7273V56.6485V39.1939V20.1879V8.16364H64V7H80V8.16364V65.1818V66.7333H77.4545V71H71.2727Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M64.7273 65.1818H64V66.7333H71.2727V71H77.4545V66.7333H80V65.1818M64.7273 65.1818H80M64.7273 65.1818V56.6485M64.7273 8.16364H64V7H80V8.16364M64.7273 8.16364H80M64.7273 8.16364V20.1879M80 65.1818V8.16364M64.7273 20.1879H74.5455M64.7273 20.1879V39.1939M64.7273 39.1939H74.5455M64.7273 39.1939V56.6485M64.7273 56.6485H74.5455" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M47.2727 71V66.7333H40V65.1818H40.7273V56.6485V39.1939V20.1879V8.16364H40V7H56V8.16364V65.1818V66.7333H53.4545V71H47.2727Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M40.7273 65.1818H40V66.7333H47.2727V71H53.4545V66.7333H56V65.1818M40.7273 65.1818H56M40.7273 65.1818V56.6485M40.7273 8.16364H40V7H56V8.16364M40.7273 8.16364H56M40.7273 8.16364V20.1879M56 65.1818V8.16364M40.7273 20.1879H50.5455M40.7273 20.1879V39.1939M40.7273 39.1939H50.5455M40.7273 39.1939V56.6485M40.7273 56.6485H50.5455" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var K1=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 140L64 140L64 128L72 128L75 124L85 124L88 128L96 128L96 140L86 140L86 148.75L74 148.75L74 140Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 21.6677C78.2643 22.1593 79.8323 23.5259 80.5811 25.3486L80.7239 25.7307L83.565 34.1692L77.6776 27.4895C76.2735 25.8965 75.7779 23.7047 76.3472 21.6677Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 45.6667C78.2643 46.1584 79.8323 47.5249 80.5811 49.3476L80.7239 49.7297L83.565 58.1682L77.6776 51.4885C76.2735 49.8955 75.7779 47.7037 76.3472 45.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 69.6667C78.2643 70.1584 79.8323 71.5249 80.5811 73.3476L80.7239 73.7297L83.565 82.1682L77.6776 75.4885C76.2735 73.8955 75.7779 71.7037 76.3472 69.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 93.6667C78.2643 94.1584 79.8323 95.5249 80.5811 97.3476L80.7239 97.7297L83.565 106.168L77.6776 99.4885C76.2735 97.8955 75.7779 95.7037 76.3472 93.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ei=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M132.366 87.1181H29.3855V83.0385L20.4844 80V71.5412H24V68.7912H20.4844V66.0412H24V51.1429H31.5L36 66.0412H48L51.5 71.5412H54.4157L55.575 61.5604L54.0915 57.1099H52.608L54.4157 54.1429H57.4294L54.4624 44.5H56.6877L61.88 54.1429C65.3312 54.1429 68.772 54.5206 72.1409 55.2692L80.4239 57.1099H78.5695L76.3443 61.5604L88.5 71.0827C102.374 69.3897 109.424 63.1236 109.424 63.1236H118L115.5 51.1429H118L122 63.1236H140.743C132 69.5 130.325 77.1044 130.325 77.1044L135.162 76.321C137.428 75.9539 139.484 77.7039 139.484 80C139.484 83.9312 136.297 87.1181 132.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M20.4844 80H139.484M20.4844 80L29.3855 83.0385V87.1181H132.366C136.297 87.1181 139.484 83.9312 139.484 80V80M20.4844 80V71.5412H24V68.7912H20.4844V66.0412H24M139.484 80V80C139.484 77.7039 137.428 75.9539 135.162 76.321L130.325 77.1044C130.325 77.1044 132 69.5 140.743 63.1236H122M54.4157 71.5412C54.4157 71.5412 75.9997 71.5 81.5 71.5C100 71.5 109.424 63.1236 109.424 63.1236H118M54.4157 71.5412L55.575 61.5604M54.4157 71.5412H51.5L48 66.0412H36M55.575 61.5604H76.3443M55.575 61.5604L54.0915 57.1099H78.5695L76.3443 61.5604M76.3443 61.5604L88.5 71.0827M61.88 54.1429V54.1429C65.3312 54.1429 68.772 54.5206 72.1409 55.2692L80.4239 57.1099H52.608L54.4157 54.1429H57.4294M61.88 54.1429L56.6877 44.5H54.4624L57.4294 54.1429M61.88 54.1429H57.4294M24 66.0412V51.1429H31.5L36 66.0412M24 66.0412H36M122 63.1236L118 51.1429H115.5L118 63.1236M122 63.1236H118" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ti=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80 18.25C80 18.25 93.5 18.25 93.5 51.1402L93.5 94.2378L93.5 122L93.5 128L93.5 135L93.5 139.75C93.5 140.855 92.6046 141.75 91.5 141.75L90.125 141.75L69.875 141.75L68.5 141.75C67.3954 141.75 66.5 140.855 66.5 139.75L66.5 135L66.5 128L66.5 122L66.5 51.1402C66.5 18.25 80 18.25 80 18.25Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 135L66.5 139.75C66.5 140.855 67.3954 141.75 68.5 141.75L69.875 141.75L90.125 141.75L91.5 141.75C92.6046 141.75 93.5 140.855 93.5 139.75L93.5 135M66.5 135L93.5 135M66.5 135L66.5 128M93.5 135L93.5 128M93.5 122L93.5 94.2378L93.5 51.1402C93.5 18.25 80 18.25 80 18.25C80 18.25 66.5 18.25 66.5 51.1402L66.5 122M93.5 122L93.5 128M93.5 122L88 122L88 128M93.5 128L88 128M66.5 128L66.5 122M66.5 128L72 128M88 128L72 128M66.5 122L72 122L72 128M82 34L81.5 42.5L78.5 42.5L78 34L82 34Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71 103.375L64.25 103.375L64.25 94.375C64.25 94.375 67.4029 89.009 69.5 86C71.7705 82.7422 75.5 78.625 75.5 78.625L84.5 78.625C84.5 78.625 87.8347 82.9839 90 86C92.2512 89.1357 95.75 94.375 95.75 94.375L95.75 103.375L89 103.375L85.625 103.5L74.375 103.5L71 103.375Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.375 103.5L71 103.375L64.25 103.375L64.25 94.375C64.25 94.375 67.4029 89.009 69.5 86C71.7705 82.7422 75.5 78.625 75.5 78.625M74.375 103.5L85.625 103.5M74.375 103.5L74.375 91C74.6384 86.5926 75.5 78.625 75.5 78.625M85.625 103.5L89 103.375L95.75 103.375L95.75 94.375C95.75 94.375 92.2512 89.1357 90 86C87.8347 82.9839 84.5 78.625 84.5 78.625M85.625 103.5L85.625 91C85.3616 86.5925 84.5 78.625 84.5 78.625M84.5 78.625L75.5 78.625" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 97.625L85.625 103.25L83.375 104.375L76.625 104.375L74.375 103.25L74.375 97.625L76.625 101L83.375 101L85.625 97.625Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 101L85.625 97.625L85.625 103.25L83.375 104.375M83.375 101L76.625 101M83.375 101L83.375 104.375M76.625 101L74.375 97.625L74.375 103.25L76.625 104.375M76.625 101L76.625 104.375M76.625 104.375L83.375 104.375" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ri=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M68 66.6364H76.2059L76.8676 65.4385L75.7206 62.1943H74.7059L77.5735 60.9964H77.9265L78.1943 59.7842C78.2956 59.3261 78.7016 59 79.1708 59H80.8292C81.2984 59 81.7044 59.3261 81.8057 59.7842L82.0735 60.9964H82.4265L85.2941 62.1943H84.2794L83.1324 65.4385L83.7941 66.6364H92V67.0856H90.6765V70.2299H92V79.3137V80.0624L91.4911 82.024C91.0722 83.639 89.8904 84.8535 88.4293 85.1706L80 87L71.5707 85.1706C70.1096 84.8535 68.9278 83.639 68.5089 82.024L68 80.0624V79.3137V70.2299V66.6364ZM73.6471 71.9657V79.3137H89.919V71.9657H73.6471Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M68 80.0624L68.5089 82.024C68.9278 83.639 70.1096 84.8535 71.5707 85.1706L80 87L88.4293 85.1706C89.8904 84.8535 91.0722 83.639 91.4911 82.024L92 80.0624M68 80.0624H92M68 80.0624V79.3137M76.2059 66.6364H68V70.2299M76.2059 66.6364L76.8676 65.4385M76.2059 66.6364H83.7941M76.8676 65.4385L75.7206 62.1943M76.8676 65.4385H83.1324M75.7206 62.1943H74.7059L77.5735 60.9964H77.9265M75.7206 62.1943H84.2794M92 80.0624V79.3137M83.7941 66.6364H92V67.0856H90.6765V70.2299M83.7941 66.6364L83.1324 65.4385M83.1324 65.4385L84.2794 62.1943M84.2794 62.1943H85.2941L82.4265 60.9964H82.0735M92 79.3137H89.919M92 79.3137V70.2299H90.6765M68 79.3137H73.6471M68 79.3137V70.2299M73.6471 79.3137V71.9657H89.919V79.3137M73.6471 79.3137H89.919M90.6765 70.2299H68M77.9265 60.9964H78.2794H81.7206H82.0735M77.9265 60.9964L78.1943 59.7842C78.2956 59.3261 78.7016 59 79.1708 59H80.8292C81.2984 59 81.7044 59.3261 81.8057 59.7842L82.0735 60.9964" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var oi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<mask id="path-1-inside-1_208_29995" fill="white">
<path d="M125.032 93.6077C139.926 93.6077 152 81.5337 152 66.6396L11.7453 66.6396L11.7453 93.6076L125.032 93.6077Z"/>
</mask>
<path d="M125.032 93.6077C139.926 93.6077 152 81.5337 152 66.6396L11.7453 66.6396L11.7453 93.6076L125.032 93.6077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M152 66.6396L154 66.6396L154 64.6396L152 64.6396L152 66.6396ZM11.7453 66.6396L11.7453 64.6396L9.74529 64.6396L9.74529 66.6396L11.7453 66.6396ZM11.7453 93.6076L9.74528 93.6076L9.74528 95.6076L11.7453 95.6076L11.7453 93.6076ZM125.032 95.6077C141.031 95.6077 154 82.6382 154 66.6396L150 66.6396C150 80.4291 138.821 91.6077 125.032 91.6077L125.032 95.6077ZM152 64.6396L11.7453 64.6396L11.7453 68.6396L152 68.6396L152 64.6396ZM9.74529 66.6396L9.74528 93.6076L13.7453 93.6076L13.7453 66.6396L9.74529 66.6396ZM11.7453 95.6076L125.032 95.6077L125.032 91.6077L11.7453 91.6076L11.7453 95.6076Z" fill="var(--instrument-tick-mark-secondary-color)" mask="url(#path-1-inside-1_208_29995)"/>
</svg>
`;var ii=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<mask id="path-1-inside-1_208_29982" fill="white">
<path fill-rule="evenodd" clip-rule="evenodd" d="M80 9.18359C71.6308 14.0249 66 23.0737 66 33.4377L66 151.06L94 151.06L94 33.4377C94 23.0737 88.3692 14.0249 80 9.18359Z"/>
</mask>
<path fill-rule="evenodd" clip-rule="evenodd" d="M80 9.18359C71.6308 14.0249 66 23.0737 66 33.4377L66 151.06L94 151.06L94 33.4377C94 23.0737 88.3692 14.0249 80 9.18359Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 9.18359L81.0014 7.45238L80 6.87307L78.9985 7.45238L80 9.18359ZM66 151.06L64 151.06L64 153.06L66 153.06L66 151.06ZM94 151.06L94 153.06L96 153.06L96 151.06L94 151.06ZM68 33.4377C68 23.8165 73.2248 15.4133 81.0014 10.9148L78.9985 7.45238C70.0367 12.6365 64 22.3309 64 33.4377L68 33.4377ZM64 33.4377L64 151.06L68 151.06L68 33.4377L64 33.4377ZM66 153.06L94 153.06L94 149.06L66 149.06L66 153.06ZM96 151.06L96 33.4377L92 33.4377L92 151.06L96 151.06ZM96 33.4377C96 22.3309 89.9633 12.6365 81.0014 7.45238L78.9985 10.9148C86.7752 15.4133 92 23.8165 92 33.4377L96 33.4377Z" fill="var(--instrument-tick-mark-secondary-color)" mask="url(#path-1-inside-1_208_29982)"/>
</svg>
`;var ai=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M67.1154 52.6364H93.8846H95L91.6538 49.2273H85.9615H75.0385H69.3462L66 52.6364H67.1154Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.1154 79.9545H93.8846V74H91.6538H69.3462H67.1154V79.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.1154 83C67.1154 85.2091 68.9062 87 71.1154 87H89.8846C92.0938 87 93.8846 85.2091 93.8846 83V79.9545H67.1154V83Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M69.3462 64H67.1154V74H69.3462V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91.6538 64V57.75H69.3462V64V74H91.6538V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M93.8846 64H91.6538V74H93.8846V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91.6538 57.75L93.8846 52.6364H67.1154L69.3462 57.75H91.6538Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M82.7308 41H78.2692L75.0385 49.2273H76.7115L79.3846 42.4205H81.6154L84.2885 49.2273H85.9615L82.7308 41Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91.6538 64H93.8846V74M91.6538 64V57.75M91.6538 64V74M91.6538 57.75L93.8846 52.6364M91.6538 57.75H69.3462M93.8846 52.6364H67.1154M93.8846 52.6364H95L91.6538 49.2273H85.9615M67.1154 52.6364L69.3462 57.75M67.1154 52.6364H66L69.3462 49.2273H75.0385M69.3462 57.75V64M69.3462 64H67.1154V74M69.3462 64V74M75.0385 49.2273H85.9615M75.0385 49.2273L78.2692 41H82.7308L85.9615 49.2273M75.0385 49.2273H76.7115L79.3846 42.4205H81.6154L84.2885 49.2273H85.9615M93.8846 79.9545V83C93.8846 85.2091 92.0938 87 89.8846 87H71.1154C68.9062 87 67.1154 85.2091 67.1154 83V79.9545M93.8846 79.9545H67.1154M93.8846 79.9545V74M67.1154 79.9545V74M67.1154 74H69.3462M93.8846 74H91.6538M91.6538 74H69.3462" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ni=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80 77.9545V87C80 87 83.744 81.9921 82.7586 80C82.1892 78.8489 80 77.9545 80 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 87V77.9545C80 77.9545 77.8682 78.8255 77.2648 79.9545C77.2567 79.9697 77.2489 79.9848 77.2414 80C76.256 81.9921 80 87 80 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 87H90.7692C92.9784 87 94.7692 85.2091 94.7692 83V80H82.7586C83.744 81.9921 80 87 80 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2308 79.9545V83C65.2308 85.2091 67.0216 87 69.2308 87H80C80 87 76.256 81.9921 77.2414 80C77.2489 79.9848 77.2567 79.9697 77.2648 79.9545H65.2308Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.6923 64H65.2308V74V79.9545H77.2648C77.8682 78.8255 80 77.9545 80 77.9545L80 64H67.6923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7692 64H92.3077H80L80 77.9545C80 77.9545 82.1892 78.8489 82.7586 80H94.7692V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 64V57.75H67.6923V64H80H92.3077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 57.75L94.7692 52.6364H65.2308L67.6923 57.75H92.3077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2308 52.6364H94.7692H96L92.3077 49.2273H86.0265H84.1804H75.8196H73.9735H67.6923L64 52.6364H65.2308Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M82.4615 41H77.5385L73.9735 49.2273H75.8196L78.7692 42.4205H81.2308L84.1804 49.2273H86.0265L82.4615 41Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92.3077 64H94.7692V74V79.9545V80M92.3077 64V57.75M92.3077 64H80M92.3077 57.75L94.7692 52.6364M92.3077 57.75H67.6923M94.7692 52.6364H65.2308M94.7692 52.6364H96L92.3077 49.2273H86.0265M65.2308 52.6364L67.6923 57.75M65.2308 52.6364H64L67.6923 49.2273H73.9735M67.6923 57.75V64M67.6923 64H65.2308V74V79.9545M67.6923 64H80M73.9735 49.2273H86.0265M73.9735 49.2273L77.5385 41H82.4615L86.0265 49.2273M73.9735 49.2273H75.8196M86.0265 49.2273H84.1804M65.2308 79.9545V83C65.2308 85.2091 67.0216 87 69.2308 87H80M65.2308 79.9545H77.2648M75.8196 49.2273L78.7692 42.4205H81.2308L84.1804 49.2273M75.8196 49.2273H84.1804M80 64L80 77.9545M80 87H90.7692C92.9784 87 94.7692 85.2091 94.7692 83V80M80 87V77.9545M80 87C80 87 83.744 81.9921 82.7586 80M80 87C80 87 76.256 81.9921 77.2414 80C77.2489 79.9848 77.2567 79.9697 77.2648 79.9545M80 77.9545C80 77.9545 82.1892 78.8489 82.7586 80M80 77.9545C80 77.9545 77.8682 78.8255 77.2648 79.9545M82.7586 80H94.7692M75.5862 72L75.0345 71H71.7241L72.2759 72H75.5862ZM83.8621 72L84.4138 71H87.7241L87.1724 72H83.8621Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var si=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71.5412H92.5943L105.575 58.5604L104.092 54.1099H102.608L104.092 52.9973H106.688V51.1429H107.429L104.462 41.5H106.688L111.88 51.1429C115.331 51.1429 118.772 51.5206 122.141 52.2692L130.424 54.1099H128.57L126.344 58.5604L131.907 64.1236H146.743C146.743 64.1236 143.808 67.7438 142.292 70.614C141.041 72.9834 139.325 77.1044 139.325 77.1044L143.176 76.4042C145.419 75.9963 147.484 77.7198 147.484 80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71.5412H92.5943M147.484 80V80C147.484 77.7198 145.419 75.9963 143.176 76.4042L139.325 77.1044C139.325 77.1044 141.041 72.9834 142.292 70.614C143.808 67.7438 146.743 64.1236 146.743 64.1236H131.907M92.5943 71.5412H97.4157L104.833 64.1236H131.907M92.5943 71.5412L105.575 58.5604M105.575 58.5604H126.344M105.575 58.5604L104.092 54.1099H128.57L126.344 58.5604M126.344 58.5604L131.907 64.1236M111.88 51.1429V51.1429C115.331 51.1429 118.772 51.5206 122.141 52.2692L130.424 54.1099H102.608L104.092 52.9973H106.688V51.1429H107.429M111.88 51.1429L106.688 41.5H104.462L107.429 51.1429M111.88 51.1429H107.429" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var li=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 74.4634L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 85.2378L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75L66.5 74.4634Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 74.4634L71 67.6585L71 61.9878L89.5625 61.9878L89.5625 81.2683L93.5 85.2378M93.5 85.2378L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 85.2378Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71 55.375L64.25 55.375L64.25 46.375L71 41.875L75.5 30.625L84.5 30.625L89 41.875L95.75 46.375L95.75 55.375L89 55.375L85.625 58.75L74.375 58.75L71 55.375Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.375 58.75L71 55.375L64.25 55.375L64.25 46.375L71 41.875L75.5 30.625M74.375 58.75L85.625 58.75M74.375 58.75L74.375 43C74.6384 38.5926 75.5 30.625 75.5 30.625M85.625 58.75L89 55.375L95.75 55.375L95.75 46.375L89 41.875L84.5 30.625M85.625 58.75L85.625 43C85.3616 38.5926 84.5 30.625 84.5 30.625M84.5 30.625L75.5 30.625" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 49.625L85.625 55.25L83.375 56.375L76.625 56.375L74.375 55.25L74.375 49.625L76.625 53L83.375 53L85.625 49.625Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 53L85.625 49.625L85.625 55.25L83.375 56.375M83.375 53L76.625 53M83.375 53L83.375 56.375M76.625 53L74.375 49.625L74.375 55.25L76.625 56.375M76.625 53L76.625 56.375M76.625 56.375L83.375 56.375" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ci=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M21.3861 87.1181H140.367C144.298 87.1181 147.485 83.9312 147.485 80C147.485 77.3161 145.721 75.4558 143.354 74.1896C142.097 73.5171 141.313 72.47 142.293 70.614C143.809 67.7438 147.485 61 147.485 61C139.641 59.2601 125.9 58.5457 110.345 58.2682V55.5604L112.57 51.1099H114.425L106.142 49.2692C102.773 48.5206 99.3318 48.1429 95.8807 48.1429L94.7268 46H102.001L104.834 43H93.0345L90.6883 38.5H88.4631L90.2323 43H74.5007V26H64.0007V71.5412H8.48505C8.48505 71.5412 7.50138 78 12.485 80L21.3861 83.0385V87.1181ZM75.8339 58.1236L74.5007 60.5354V48.1429V46H90.7708L91.4301 48.1429H89.6883L86.6883 49.9973H77.0922L75.6087 51.1099H77.0922L78.5757 55.5604V58.1199C77.6695 58.1223 76.7557 58.1236 75.8339 58.1236Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.485 80C65.2058 80 147.485 80 147.485 80M12.485 80C15.9611 81.1866 21.3861 83.0385 21.3861 83.0385M12.485 80C7.50138 78 8.48505 71.5412 8.48505 71.5412H64.0007M12.485 80L21.3861 83.0385M147.485 80V80C147.485 83.9312 144.298 87.1181 140.367 87.1181V87.1181M147.485 80V80C147.485 77.3161 145.721 75.4557 143.354 74.1896V74.1896M147.485 80C147.485 77.3161 145.721 75.4558 143.354 74.1896M147.485 80C147.485 83.9312 144.298 87.1181 140.367 87.1181M21.3861 83.0385V87.1181H140.367M147.485 61C147.485 61 143.809 67.7438 142.293 70.614C141.313 72.47 142.097 73.5171 143.354 74.1896M147.485 61C134.501 58.1199 105.36 58.0499 78.5757 58.1199M147.485 61C139.641 59.2601 125.9 58.5457 110.345 58.2682V55.5604M78.5757 55.5604H110.345M78.5757 55.5604L77.0922 51.1099M78.5757 55.5604V58.1199M110.345 55.5604L112.57 51.1099M112.57 51.1099H77.0922M112.57 51.1099H114.425M77.0922 51.1099H75.6087M75.6087 51.1099H114.425M75.6087 51.1099L77.0922 49.9973H86.6883L89.6883 48.1429H91.4301M114.425 51.1099L106.142 49.2692M95.8807 48.1429V48.1429C99.3318 48.1429 102.773 48.5206 106.142 49.2692V49.2692M95.8807 48.1429H91.4301M95.8807 48.1429L94.7268 46M95.8807 48.1429C99.3318 48.1429 102.773 48.5206 106.142 49.2692M91.4301 48.1429L90.7708 46M64.0007 71.5412V26H74.5007V43M64.0007 71.5412H68.4164L74.5007 60.5354M74.5007 46V48.1429V60.5354M74.5007 46V43M74.5007 46H90.7708M74.5007 43H90.2323M93.0345 43H104.834L102.001 46H94.7268M93.0345 43L90.6883 38.5H88.4631L90.2323 43M93.0345 43H90.2323M90.7708 46H94.7268M74.5007 60.842V60.5354M78.5757 58.1199C77.6695 58.1223 76.7557 58.1236 75.8339 58.1236L74.5007 60.5354" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var di=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 81L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 81L93.5 135.25C93.5 142.706 87.4558 148.75 80 148.75C72.5442 148.75 66.5 142.706 66.5 135.25L66.5 81Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 81L73 81L73 77.9878L87 77.9878L87 81L93.5 81M93.5 81L93.5 135.25C93.5 142.706 87.4558 148.75 80 148.75V148.75C72.5442 148.75 66.5 142.706 66.5 135.25L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 81Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74.375 80.125L71.5 84L67 84L64 80L64 65L71 59.25L75.5 46L84.5 46L89 59.25L96 65L96 80.125L93 84L88.5 84L85.625 80.125L85.625 76L74.375 76L74.375 80.125Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M84.5 46L89 59.25L96 65L96 80.125L93 84L88.5 84L85.625 80.125L85.625 76M84.5 46L75.5 46M84.5 46C84.5 46 85.3616 55.5926 85.625 60L85.625 76M75.5 46L71 59.25L64 65L64 80L67 84L71.5 84L74.375 80.125L74.375 76M75.5 46C75.5 46 74.6384 55.5926 74.375 60L74.375 76M74.375 76L85.625 76" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 65L85.625 70.625L83.375 71.75L76.625 71.75L74.375 70.625L74.375 65L76.625 68.375L83.375 68.375L85.625 65Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 68.375L85.625 65L85.625 70.625L83.375 71.75M83.375 68.375L76.625 68.375M83.375 68.375L83.375 71.75M76.625 68.375L74.375 65L74.375 70.625L76.625 71.75M76.625 68.375L76.625 71.75M76.625 71.75L83.375 71.75" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="82.4185" y="91.8209" width="5" height="31" transform="rotate(-150 82.4185 91.8209)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="79.9992" cy="91.0031" r="5.5" transform="rotate(-150 79.9992 91.0031)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var pi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect x="60" y="52" width="40" height="3" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M80.0036 77.9545V87C80.0036 87 83.7476 81.9921 82.7622 80C82.1928 78.8489 80.0036 77.9545 80.0036 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87V77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545C77.2603 79.9697 77.2525 79.9848 77.245 80C76.2596 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80H82.7622C83.7476 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545H65.2344Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M69 64H65.2344V74V79.9545H77.2684C77.8718 78.8255 80.0036 77.9545 80.0036 77.9545L80.0036 64H69Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7728 64H91H80.0036L80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80H94.7728V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 64V52H69V64H80.0036H91Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 52L94 49H66L69 52H91Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66 49H94H94.7728L93 47.2273H83.0301H81.184H78.8232H76.9771H67.133L65.2344 49H66Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.0301 39H77.0036L76.9771 47.2273H78.8232L78.7728 40.4205H81.2344L81.184 47.2273H83.0301V39Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91 64H94.7728V74V79.9545V80M91 64V52M91 64H80.0036M91 52L94 49M91 52H69M94 49H66M94 49H94.7728L93 47.2273H83.0301M66 49L69 52M66 49H65.2344L67.133 47.2273H76.9771M69 52V64M69 64H65.2344V74V79.9545M69 64H80.0036M76.9771 47.2273H83.0301M76.9771 47.2273L77.0036 39H83.0301V47.2273M76.9771 47.2273H78.8232M83.0301 47.2273H81.184M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036M65.2344 79.9545H77.2684M78.8232 47.2273L78.7728 40.4205H81.2344L81.184 47.2273M78.8232 47.2273H81.184M80.0036 64L80.0036 77.9545M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80M80.0036 87V77.9545M80.0036 87C80.0036 87 83.7476 81.9921 82.7622 80M80.0036 87C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545M80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80M80.0036 77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545M82.7622 80H94.7728" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M80.0036 77.9545V87C80.0036 87 83.7476 81.9921 82.7622 80C82.1928 78.8489 80.0036 77.9545 80.0036 77.9545Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87V77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545C77.2603 79.9697 77.2525 79.9848 77.245 80C76.2596 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80H82.7622C83.7476 81.9921 80.0036 87 80.0036 87Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545H65.2344Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M94.7728 64H92.3113H80.0036L80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80H94.7728V79.9545V74V64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M65.2344 79.9545V83C65.2344 85.2091 67.0252 87 69.2344 87H80.0036M65.2344 79.9545V74V64H67.6959H80.0036M65.2344 79.9545H77.2684M80.0036 64H92.3113H94.7728V74V79.9545V80M80.0036 64L80.0036 77.9545M80.0036 87H90.7728C92.982 87 94.7728 85.2091 94.7728 83V80M80.0036 87V77.9545M80.0036 87C80.0036 87 83.7476 81.9921 82.7622 80M80.0036 87C80.0036 87 76.2596 81.9921 77.245 80C77.2525 79.9848 77.2603 79.9697 77.2684 79.9545M80.0036 77.9545C80.0036 77.9545 82.1928 78.8489 82.7622 80M80.0036 77.9545C80.0036 77.9545 77.8718 78.8255 77.2684 79.9545M82.7622 80H94.7728" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M92.09 64H67.8359C70.2566 59.8154 74.781 57 79.963 57C85.145 57 89.6694 59.8154 92.09 64Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M67.8359 64L67.4031 63.7496L66.9691 64.5H67.8359V64ZM92.09 64V64.5H92.9569L92.5228 63.7496L92.09 64ZM67.8359 64.5H92.09V63.5H67.8359V64.5ZM68.2687 64.2504C70.6037 60.2139 74.9667 57.5 79.963 57.5V56.5C74.5953 56.5 69.9095 59.4169 67.4031 63.7496L68.2687 64.2504ZM79.963 57.5C84.9593 57.5 89.3223 60.2139 91.6572 64.2504L92.5228 63.7496C90.0165 59.4169 85.3307 56.5 79.963 56.5V57.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="87.498" cy="70.0003" rx="1.5" ry="2" transform="rotate(45 87.498 70.0003)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="72.4983" cy="70" rx="1.5" ry="2" transform="rotate(-45 72.4983 70)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M96 55L91 60" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M64 55L69 60" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var hi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M53.0312 72H80.9609C80.4482 64.7347 74.3918 59 66.9961 59C59.6003 59 53.544 64.7347 53.0312 72ZM139.961 72C139.448 64.7347 133.392 59 125.996 59C118.6 59 112.544 64.7347 112.031 72H139.961ZM110.961 72C110.448 64.7347 104.392 59 96.9961 59C89.6003 59 83.544 64.7347 83.0312 72H110.961Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M53.0312 72L52.5325 71.9648L52.4947 72.5H53.0312V72ZM80.9609 72V72.5H81.4975L81.4597 71.9648L80.9609 72ZM139.961 72V72.5H140.497L140.46 71.9648L139.961 72ZM112.031 72L111.532 71.9648L111.495 72.5H112.031V72ZM110.961 72V72.5H111.497L111.46 71.9648L110.961 72ZM83.0312 72L82.5325 71.9648L82.4947 72.5H83.0312V72ZM53.0312 72.5H80.9609V71.5H53.0312V72.5ZM81.4597 71.9648C80.9286 64.4396 74.6562 58.5 66.9961 58.5V59.5C74.1275 59.5 79.9678 65.0299 80.4622 72.0352L81.4597 71.9648ZM66.9961 58.5C59.336 58.5 53.0636 64.4396 52.5325 71.9648L53.53 72.0352C54.0244 65.0299 59.8647 59.5 66.9961 59.5V58.5ZM140.46 71.9648C139.929 64.4396 133.656 58.5 125.996 58.5V59.5C133.127 59.5 138.968 65.0299 139.462 72.0352L140.46 71.9648ZM125.996 58.5C118.336 58.5 112.064 64.4396 111.532 71.9648L112.53 72.0352C113.024 65.0299 118.865 59.5 125.996 59.5V58.5ZM112.031 72.5H139.961V71.5H112.031V72.5ZM111.46 71.9648C110.929 64.4396 104.656 58.5 96.9961 58.5V59.5C104.127 59.5 109.968 65.0299 110.462 72.0352L111.46 71.9648ZM96.9961 58.5C89.336 58.5 83.0636 64.4396 82.5325 71.9648L83.53 72.0352C84.0244 65.0299 89.8647 59.5 96.9961 59.5V58.5ZM83.0312 72.5H110.961V71.5H83.0312V72.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71H18.4844V63L22 44H26V63H32.4844V53.5604V50.1099L31 48.9973L32 48.1429H37.4294L37.2747 38.5H39.5L41.88 48.1429H45.8152C48.7962 48.1429 51.7388 48.8152 54.4239 50.1099H52.5695L50.3443 53.5604V71H117.416L124.833 64.1236H148C148 64.1236 148 68.5 145.5 71C143.605 72.8947 143.5 75.6209 143.5 75.6209C145.701 75.6209 147.484 77.4047 147.484 79.6053V80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71H18.4844M147.484 80V79.6053C147.484 77.4047 145.701 75.6209 143.5 75.6209V75.6209C143.5 75.6209 143.605 72.8947 145.5 71C148 68.5 148 64.1236 148 64.1236H124.833L117.416 71H50.3443M18.4844 71H50.3443M18.4844 71V63L22 44H26V63H32.4844V53.5604M32.4844 53.5604H50.3443M32.4844 53.5604V50.1099M50.3443 53.5604L52.5695 50.1099H32.4844M50.3443 53.5604V71M32.4844 50.1099H54.4239V50.1099C51.7388 48.8152 48.7962 48.1429 45.8152 48.1429H41.88M32.4844 50.1099L31 48.9973L32 48.1429H37.4294M41.88 48.1429L39.5 38.5H37.2747L37.4294 48.1429M41.88 48.1429H37.4294" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="136" cy="70" r="2" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ui=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 122L64 122L64 118L72 118L75 114L85 114L88 118L96 118L96 122L86 122L86 138.75L74 138.75L74 122Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="44" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="70" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="96" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var vi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1182H21.3855V83.0386L12.4844 80.0001C12.4844 77.5441 14.487 75.5592 16.943 75.5812L21.3855 75.621L84.5943 75.5413L96.8333 64.1237H100.012V49.5H101H103H105.575L106.76 54.5605H115.281C122.13 54.5605 128.463 58.203 131.907 64.1237H138C141.233 66.387 144.251 70.5308 145.98 73.1767C147.01 74.7539 147.484 76.6105 147.484 78.4946V80.0001C147.484 83.9313 144.297 87.1182 140.366 87.1182Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80.0001H147.484M12.4844 80.0001L21.3855 83.0386V87.1182H140.366C144.297 87.1182 147.484 83.9313 147.484 80.0001V80.0001M12.4844 80.0001V80.0001C12.4844 77.5441 14.487 75.5592 16.943 75.5812L21.3855 75.621L84.5943 75.5413L96.8333 64.1237H100.012M147.484 80.0001V78.4946C147.484 76.6105 147.01 74.7539 145.98 73.1767C144.251 70.5308 141.233 66.387 138 64.1237H131.907M106.76 54.5605H115.281C122.13 54.5605 128.463 58.203 131.907 64.1237V64.1237M131.907 64.1237H109M100.012 64.1237V49.5H101M100.012 64.1237H109M109 64.1237L105.575 49.5H103M101 49.5V45M101 49.5H103M103 49.5V47" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var mi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M147.484 80.0001L146.814 81.5981C145.412 84.9422 142.14 87.1182 138.514 87.1182H21.3855V83.0386L12.4844 80.0001C12.4844 77.5376 14.4806 75.5413 16.9432 75.5413H21L30.5 56.5H32H34.5H36.5L33.5 75.5413H36.5943L48.8333 64.1237H100.012H127.5L145.461 66.8188C147.93 67.1894 149.587 69.5517 149.094 72L147.484 80.0001Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80.0001L21.3855 83.0386V87.1182H138.514C142.14 87.1182 145.412 84.9422 146.814 81.5981L147.484 80.0001L149.094 72M12.4844 80.0001V80.0001C12.4844 77.5376 14.4806 75.5413 16.9432 75.5413H21M12.4844 80.0001H107.04C116.302 80.0001 125.519 78.7134 134.427 76.1768L149.094 72M21 75.5413L30.5 56.5H32M21 75.5413H33.5M33.5 75.5413H36.5943L48.8333 64.1237H100.012H127.5L145.461 66.8188C147.93 67.1894 149.587 69.5517 149.094 72V72M33.5 75.5413L36.5 56.5H34.5M34.5 56.5V48.5M34.5 56.5H32M32 56.5V53" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var fi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M121.033 100.2L101 80H96L118.289 99.8667C118.741 100.27 119 100.846 119 101.452V102.835C119 103.478 119.522 104 120.165 104C120.809 104 121.33 103.478 121.33 102.835V100.922C121.33 100.652 121.223 100.392 121.033 100.2Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M39.2975 100.2L59.3301 80H64.3301L42.0407 99.8667C41.5887 100.27 41.3301 100.846 41.3301 101.452V102.835C41.3301 103.478 40.8085 104 40.1651 104C39.5216 104 39 103.478 39 102.835V100.922C39 100.652 39.1069 100.392 39.2975 100.2Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M121.033 100.2L101 80H96L118.289 99.8667C118.741 100.27 119 100.846 119 101.452V102.835C119 103.478 119.522 104 120.165 104C120.809 104 121.33 103.478 121.33 102.835V100.922C121.33 100.652 121.223 100.392 121.033 100.2Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M39.2975 100.2L59.3301 80H64.3301L42.0407 99.8667C41.5887 100.27 41.3301 100.846 41.3301 101.452V102.835C41.3301 103.478 40.8085 104 40.1651 104C39.5216 104 39 103.478 39 102.835V100.922C39 100.652 39.1069 100.392 39.2975 100.2Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M118 64H126V77.8755C126 79.2677 125.637 80.6358 124.946 81.8446L123.736 83.9611C122.969 85.3048 121.031 85.3048 120.264 83.9611L119.054 81.8446C118.363 80.6358 118 79.2677 118 77.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M34 64H42V77.8755C42 79.2677 41.6367 80.6358 40.9459 81.8446L39.7365 83.9611C38.9687 85.3048 37.0313 85.3048 36.2635 83.9611L35.0541 81.8446C34.3633 80.6358 34 79.2677 34 77.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M134 75.1317V73H120L98 70V73L90 79.9999L132.136 77.127C133.185 77.0555 134 76.1834 134 75.1317Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M98 73L90 79.9999L132.136 77.127C133.185 77.0555 134 76.1834 134 75.1317V73H120M98 73H120M98 73V70L120 73" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M26 75.1346V73H40L62 70V73L69 79.9999L27.8608 77.1298C26.8128 77.0567 26 76.1852 26 75.1346Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M62 73L69 79.9999L27.8608 77.1298C26.8128 77.0567 26 76.1852 26 75.1346V73H40M62 73H40M62 73V70L40 73" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M93.039 84.5757L97.8383 73.3773C97.945 73.1284 98 72.8603 98 72.5895V68.9075C98 68.3308 97.751 67.7822 97.317 67.4024L90.5655 61.4948C90.201 61.1758 89.733 61 89.2485 61H70.7585C70.2698 61 69.798 61.1789 69.4322 61.503L62.6737 67.491C62.2453 67.8706 62 68.4156 62 68.988V73L66.961 84.5757C67.5913 86.0464 69.0375 87 70.6376 87H89.3624C90.9625 87 92.4087 86.0464 93.039 84.5757Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="12.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="96.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M70 61L72.7396 65.1094C73.1105 65.6658 73.735 66 74.4037 66H85.5963C86.265 66 86.8895 65.6658 87.2604 65.1094L90 61" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M62 68H98" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="79" rx="6" ry="6" transform="rotate(90 80 79)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="79" rx="4" ry="4" transform="rotate(90 80 79)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="81" cy="78" rx="2" ry="2" transform="rotate(90 81 78)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var gi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M131 75C133.209 75 135 76.7909 135 79C135 81.2091 133.209 83 131 83V75Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M132 84V74C132 73.4477 131.552 73 131 73H89L98.7002 84.6402C98.8901 84.8682 99.1716 85 99.4684 85H131C131.552 85 132 84.5523 132 84Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M129.736 73.4611L122.576 85.9923C122.22 86.6154 121.557 87 120.839 87H69.8301C69.2805 87 68.7346 86.9094 68.2144 86.7317L28 73V68.0879L29.1795 65.9233C30.0014 64.415 31.5399 63.4342 33.2542 63.3257L70 61H90L124.906 65.3632C125.627 65.4533 126.319 65.6995 126.935 66.0846L129.925 67.9534C129.972 67.9824 130 68.0332 130 68.0879V72.4689C130 72.8169 129.909 73.159 129.736 73.4611Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M28 68.0879V73L68.2144 86.7317C68.7346 86.9094 69.2805 87 69.8301 87H120.839C121.557 87 122.22 86.6154 122.576 85.9923L129.736 73.4611C129.909 73.159 130 72.8169 130 72.4689V68.0879M28 68.0879L29.1795 65.9233C30.0014 64.415 31.5399 63.4342 33.2542 63.3257L70 61H90L124.906 65.3632C125.627 65.4533 126.319 65.6995 126.935 66.0846L129.925 67.9534C129.972 67.9824 130 68.0332 130 68.0879M28 68.0879H130" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M128.918 100.202L101 80H96L126.097 99.9027C126.661 100.276 127 100.907 127 101.583V102.835C127 103.478 127.522 104 128.165 104C128.809 104 129.33 103.478 129.33 102.835V101.009C129.33 100.689 129.177 100.389 128.918 100.202Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M31.4125 100.202L59.3301 80H64.3301L34.2334 99.9027C33.6694 100.276 33.3301 100.907 33.3301 101.583V102.835C33.3301 103.478 32.8085 104 32.1651 104C31.5216 104 31 103.478 31 102.835V101.009C31 100.689 31.1534 100.389 31.4125 100.202Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M128.918 100.202L101 80H96L126.097 99.9027C126.661 100.276 127 100.907 127 101.583V102.835C127 103.478 127.522 104 128.165 104C128.809 104 129.33 103.478 129.33 102.835V101.009C129.33 100.689 129.177 100.389 128.918 100.202Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M31.4125 100.202L59.3301 80H64.3301L34.2334 99.9027C33.6694 100.276 33.3301 100.907 33.3301 101.583V102.835C33.3301 103.478 32.8085 104 32.1651 104C31.5216 104 31 103.478 31 102.835V101.009C31 100.689 31.1534 100.389 31.4125 100.202Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M118 64H126V73.8755C126 75.2677 125.637 76.6358 124.946 77.8446L123.736 79.9611C122.969 81.3048 121.031 81.3048 120.264 79.9611L119.054 77.8446C118.363 76.6358 118 75.2677 118 73.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M34 64H42V73.8755C42 75.2677 41.6367 76.6358 40.9459 77.8446L39.7365 79.9611C38.9687 81.3048 37.0313 81.3048 36.2635 79.9611L35.0541 77.8446C34.3633 76.6358 34 75.2677 34 73.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M127 75.1731V73.9996C127 73.4473 126.552 72.9996 126 72.9996H120L98 70V72.9996L94 79.9996L125.181 77.1649C126.211 77.0713 127 76.2076 127 75.1731Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M98 72.9996L94 79.9996L125.181 77.1649C126.211 77.0713 127 76.2076 127 75.1731V73.9996C127 73.4473 126.552 72.9996 126 72.9996H120M98 72.9996H120M98 72.9996V70L120 72.9996" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M32 75.1735V74C32 73.4477 32.4477 73 33 73H40L62 70V73L65 79.9999L33.8189 77.1653C32.7888 77.0717 32 76.2079 32 75.1735Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M62 73L65 79.9999M62 73H40M62 73V70M62 73H98M65 79.9999L33.8189 77.1653C32.7888 77.0717 32 76.2079 32 75.1735V74C32 73.4477 32.4477 73 33 73H40M65 79.9999H94M40 73L62 70M62 70H98" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="12.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="96.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var bi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="80" cy="25" rx="4" ry="4" transform="rotate(90 80 25)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M87.5 26L87.5 50C87.5 50.8284 86.8284 51.5 86 51.5L74 51.5C73.1716 51.5 72.5 50.8284 72.5 50L72.5 26C72.5 25.1716 73.1716 24.5 74 24.5L86 24.5C86.8284 24.5 87.5 25.1716 87.5 26Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<g clip-path="url(#clip0_25406_62468)">
<path d="M74.124 68.9067L34.8998 38.5288C34.1757 37.968 33.974 36.9602 34.4265 36.164C34.8921 35.3447 35.9013 35.0093 36.7647 35.387L81.9764 55.1651C82.5202 55.403 82.7383 56.0593 82.4451 56.5754L75.6058 68.6102C75.305 69.1394 74.6053 69.2794 74.124 68.9067Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.124 91.0923L34.8998 121.47C34.1757 122.031 33.974 123.039 34.4265 123.835C34.8921 124.654 35.9013 124.99 36.7647 124.612L81.9764 104.834C82.5202 104.596 82.7383 103.94 82.4451 103.424L75.6058 91.3888C75.305 90.8597 74.6053 90.7196 74.124 91.0923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8757 68.9067L125.1 38.5288C125.824 37.968 126.026 36.9602 125.573 36.164C125.108 35.3447 124.098 35.0093 123.235 35.387L78.0233 55.1651C77.4795 55.403 77.2614 56.0593 77.5546 56.5754L84.394 68.6102C84.6947 69.1394 85.3945 69.2794 85.8757 68.9067Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8757 91.0923L125.1 121.47C125.824 122.031 126.026 123.039 125.573 123.835C125.108 124.654 124.098 124.99 123.235 124.612L78.0233 104.834C77.4795 104.596 77.2614 103.94 77.5546 103.424L84.394 91.3889C84.6947 90.8597 85.3945 90.7196 85.8757 91.0923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.124 68.9067L34.8998 38.5288C34.1757 37.968 33.974 36.9602 34.4265 36.164C34.8921 35.3447 35.9013 35.0093 36.7647 35.387L81.9764 55.1651C82.5202 55.403 82.7383 56.0593 82.4451 56.5754L75.6058 68.6102C75.305 69.1394 74.6053 69.2794 74.124 68.9067Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74.124 91.0923L34.8998 121.47C34.1757 122.031 33.974 123.039 34.4265 123.835C34.8921 124.654 35.9013 124.99 36.7647 124.612L81.9764 104.834C82.5202 104.596 82.7383 103.94 82.4451 103.424L75.6058 91.3888C75.305 90.8597 74.6053 90.7196 74.124 91.0923Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.8757 68.9067L125.1 38.5288C125.824 37.968 126.026 36.9602 125.573 36.164C125.108 35.3447 124.098 35.0093 123.235 35.387L78.0233 55.1651C77.4795 55.403 77.2614 56.0593 77.5546 56.5754L84.394 68.6102C84.6947 69.1394 85.3945 69.2794 85.8757 68.9067Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.8757 91.0923L125.1 121.47C125.824 122.031 126.026 123.039 125.573 123.835C125.108 124.654 124.098 124.99 123.235 124.612L78.0233 104.834C77.4795 104.596 77.2614 103.94 77.5546 103.424L84.394 91.3889C84.6947 90.8597 85.3945 90.7196 85.8757 91.0923Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71.3558 28C69.4149 28 67.7537 29.3933 67.4163 31.3047L62.3011 60.292C62.1088 61.3815 62.3765 62.5026 63.0404 63.3877L67.1995 68.9336C67.7188 69.6259 68.0003 70.4676 68.0003 71.333V88.667C68.0003 89.5324 67.7188 90.3741 67.1995 91.0664L63.0404 96.6123C62.3765 97.4974 62.1088 98.6185 62.3011 99.708L67.4163 128.695C67.7537 130.607 69.4149 132 71.3558 132H88.6439C90.5848 132 92.246 130.607 92.5833 128.695L97.6986 99.708C97.8908 98.6185 97.6231 97.4974 96.9593 96.6123L92.8001 91.0664C92.2809 90.3741 92.0004 89.5323 92.0003 88.667V71.333C92.0004 70.4677 92.2809 69.6259 92.8001 68.9336L96.9593 63.3877C97.6231 62.5026 97.8908 61.3815 97.6986 60.292L92.5833 31.3047C92.246 29.3933 90.5848 28 88.6439 28H71.3558Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M90 69.72L85.6046 34.7506C85.4789 33.7503 84.6284 33 83.6203 33H75.4038C74.3746 33 73.5134 33.7811 73.4132 34.8054L70 69.72V127C70 128.105 70.8954 129 72 129H88C89.1046 129 90 128.105 90 127V69.72Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M19.9688 103.969C10.0104 113.927 10.0104 130.073 19.9688 140.031C29.9271 149.99 46.0729 149.99 56.0312 140.031C65.9896 130.073 65.9896 113.927 56.0312 103.969C46.0729 94.0104 29.9271 94.0104 19.9688 103.969ZM20.6759 104.676C30.2437 95.108 45.7563 95.108 55.3241 104.676C64.892 114.244 64.892 129.756 55.3241 139.324C45.7563 148.892 30.2437 148.892 20.6759 139.324C11.108 129.756 11.108 114.244 20.6759 104.676ZM21.5501 105.112C20.9439 105.42 20.8152 106.231 21.296 106.712L33.8271 119.243C33.4283 119.845 33.1745 120.516 33.0641 121.204L32.5379 121.24C31.9638 121.279 31.4336 121.563 31.0836 122.019L20.8333 135.403C20.3658 136.014 20.2899 136.839 20.6379 137.525L21.1109 138.457C21.419 139.062 22.2289 139.191 22.7095 138.71L35.2455 126.174C35.8448 126.571 36.511 126.823 37.1955 126.934L37.2307 127.461C37.2693 128.035 37.5541 128.565 38.011 128.915L51.3936 139.165C52.0042 139.633 52.8299 139.709 53.5156 139.361L54.4471 138.888C55.0531 138.58 55.1821 137.77 54.7019 137.289L42.1701 124.757C42.5663 124.159 42.8208 123.494 42.9325 122.81L43.4587 122.775C44.033 122.737 44.5636 122.453 44.9136 121.996L55.1632 108.613C55.6308 108.002 55.7071 107.177 55.3593 106.491L54.8863 105.56C54.5784 104.954 53.7685 104.824 53.2877 105.305L40.7614 117.831C40.1593 117.431 39.4894 117.175 38.801 117.064L38.7658 116.54C38.7274 115.966 38.4435 115.436 37.9869 115.086L24.603 104.835C23.9924 104.368 23.1681 104.292 22.4823 104.64L21.5501 105.112Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="38" cy="122" r="2.5" transform="rotate(-135 38 122)" vector-effect="non-scaling-stroke" stroke="var(--instrument-frame-primary-color)"/>
<path d="M38 12.5C23.9167 12.5 12.5 23.9167 12.5 38C12.5 52.0833 23.9167 63.5 38 63.5C52.0833 63.5 63.5 52.0833 63.5 38C63.5 23.9167 52.0833 12.5 38 12.5ZM38 13.5C51.531 13.5 62.5 24.469 62.5 38C62.5 51.531 51.531 62.5 38 62.5C24.469 62.5 13.5 51.531 13.5 38C13.5 24.469 24.469 13.5 38 13.5ZM38.3096 14.4258C37.6634 14.2154 37 14.6973 37 15.377V33.1006C36.2943 33.244 35.6428 33.5359 35.0791 33.9424L34.6826 33.5967C34.2495 33.2177 33.6731 33.0437 33.1025 33.1191L16.3916 35.335C15.6291 35.436 14.9918 35.9652 14.7529 36.6963L14.4287 37.6895C14.2177 38.3358 14.6991 38.9998 15.3789 39H33.1006C33.2438 39.7055 33.5362 40.3564 33.9424 40.9199L33.5957 41.3164C33.2169 41.7497 33.0425 42.3259 33.1182 42.8965L35.334 59.6074C35.4351 60.3698 35.9653 61.0072 36.6963 61.2461L37.6895 61.5703C38.3356 61.7807 39 61.2988 39 60.6191V42.8984C39.7062 42.7546 40.3589 42.4628 40.9229 42.0557L41.3193 42.4033C41.7525 42.7821 42.328 42.9564 42.8984 42.8809L59.6104 40.665C60.3724 40.5636 61.0093 40.0345 61.248 39.3037L61.5732 38.3105C61.7841 37.6644 61.3016 37.0004 60.6221 37H42.8994C42.756 36.2934 42.4638 35.6403 42.0566 35.0762L42.4033 34.6797C42.7822 34.2464 42.9565 33.6702 42.8809 33.0996L40.665 16.3887C40.5639 15.6263 40.0337 14.9889 39.3027 14.75L38.3096 14.4258Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="38" cy="38" r="2.5" transform="rotate(-90 38 38)" vector-effect="non-scaling-stroke" stroke="var(--instrument-frame-primary-color)"/>
<path d="M144.084 109.248C137.042 97.0519 121.447 92.8731 109.25 99.9147C97.0539 106.956 92.8751 122.552 99.9167 134.748C106.958 146.945 122.554 151.124 134.75 144.082C146.947 137.04 151.126 121.445 144.084 109.248ZM143.218 109.748C149.983 121.467 145.969 136.451 134.25 143.216C122.532 149.981 107.548 145.967 100.783 134.248C94.0172 122.53 98.0322 107.546 109.75 100.781C121.469 94.0153 136.452 98.0302 143.218 109.748ZM142.571 110.481C142.43 109.815 141.681 109.481 141.092 109.821L125.745 118.682C125.268 118.142 124.687 117.725 124.053 117.44L124.155 116.923C124.266 116.358 124.129 115.772 123.778 115.316L113.503 101.951C113.034 101.341 112.258 101.055 111.505 101.213L110.483 101.429C109.818 101.57 109.484 102.318 109.823 102.907L118.684 118.255C118.145 118.731 117.727 119.31 117.442 119.943L116.926 119.842C116.361 119.73 115.776 119.867 115.319 120.217L101.954 130.492C101.345 130.961 101.058 131.738 101.217 132.49L101.432 133.513C101.572 134.178 102.322 134.512 102.911 134.172L118.256 125.312C118.734 125.853 119.314 126.272 119.949 126.557L119.846 127.073C119.734 127.638 119.871 128.224 120.222 128.68L130.497 142.045C130.966 142.655 131.743 142.941 132.496 142.782L133.518 142.567C134.183 142.426 134.517 141.677 134.177 141.089L125.316 125.741C125.855 125.263 126.275 124.684 126.56 124.05L127.077 124.152C127.641 124.264 128.228 124.126 128.684 123.776L142.049 113.501C142.658 113.032 142.945 112.255 142.786 111.503L142.571 110.481Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="122" cy="121.998" r="2.5" transform="rotate(-30 122 121.998)" vector-effect="non-scaling-stroke" stroke="var(--instrument-frame-primary-color)"/>
<path d="M128.6 13.3669C114.996 9.72189 101.014 17.7947 97.3689 31.3981C93.7241 45.0014 101.797 58.9842 115.4 62.6291C129.003 66.274 142.986 58.201 146.631 44.5979C150.276 30.9946 142.203 17.012 128.6 13.3669ZM128.341 14.3328C141.411 17.835 149.167 31.2692 145.665 44.3391C142.163 57.4087 128.729 65.1651 115.659 61.6632C102.589 58.1612 94.833 44.7267 98.3348 31.657C101.837 18.587 115.271 10.8308 128.341 14.3328ZM128.4 15.3081C127.831 14.9376 127.065 15.2315 126.889 15.888L122.302 33.0058C121.584 32.9617 120.879 33.075 120.229 33.3217L119.935 32.884C119.614 32.406 119.103 32.0885 118.532 32.0138L101.817 29.829C101.055 29.7294 100.302 30.0765 99.8817 30.7208L99.3115 31.5962C98.9407 32.1657 99.234 32.9308 99.8904 33.107L117.008 37.6937C116.964 38.4135 117.078 39.119 117.326 39.7695L116.888 40.0627C116.41 40.3831 116.093 40.8945 116.018 41.4653L113.832 58.1801C113.732 58.9428 114.079 59.6956 114.724 60.1155L115.599 60.6858C116.169 61.0566 116.935 60.7628 117.111 60.1062L121.698 42.9874C122.417 43.0311 123.123 42.9179 123.773 42.6708L124.066 43.1092C124.386 43.5871 124.897 43.9045 125.468 43.9792L142.184 46.1642C142.946 46.2637 143.698 45.9172 144.118 45.2732L144.689 44.398C145.06 43.8284 144.766 43.062 144.109 42.8859L126.992 38.2992C127.036 37.58 126.923 36.874 126.676 36.224L127.112 35.9315C127.59 35.611 127.908 35.0995 127.983 34.5288L130.167 17.8138C130.267 17.0512 129.92 16.2983 129.276 15.8784L128.4 15.3081Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="122" cy="37.9978" r="2.5" transform="rotate(-75 122 37.9978)" vector-effect="non-scaling-stroke" stroke="var(--instrument-frame-primary-color)"/>
</g>
<defs>
<clipPath id="clip0_25406_62468">
<rect width="160" height="160" fill="var(--instrument-frame-primary-color)" transform="matrix(-1 0 0 1 160 0)"/>
</clipPath>
</defs>
</svg>
`;var Ci=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M44 66.5C44 65.6716 44.6716 65 45.5 65C46.3284 65 47 65.6716 47 66.5V73H44V66.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M53.4165 67.8786L68.1048 66.6196C68.2285 66.609 68.226 66.4272 68.102 66.4201L52.9506 65.5543C52.3191 65.5182 51.6855 65.5572 51.0632 65.6703L46.5 66.5L50.6284 67.6259C51.5357 67.8734 52.4795 67.9589 53.4165 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M37.0835 67.8786L22.3952 66.6196C22.2715 66.609 22.2741 66.4272 22.398 66.4201L37.5494 65.5543C38.1809 65.5182 38.8145 65.5572 39.4368 65.6703L44 66.5L39.8716 67.6259C38.9643 67.8734 38.0205 67.9589 37.0835 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M44 66.5V73H47V66.5C47 65.6716 46.3284 65 45.5 65C44.6716 65 44 65.6716 44 66.5ZM44 66.5L39.8716 67.6259C38.9643 67.8734 38.0205 67.9589 37.0835 67.8786L22.3952 66.6196C22.2715 66.609 22.2741 66.4272 22.398 66.4201L37.5494 65.5543C38.1809 65.5182 38.8145 65.5572 39.4368 65.6703L44 66.5ZM68.1048 66.6196L53.4165 67.8786C52.4795 67.9589 51.5357 67.8734 50.6284 67.6259L46.5 66.5L51.0632 65.6703C51.6855 65.5572 52.3191 65.5182 52.9506 65.5543L68.102 66.4201C68.226 66.4272 68.2285 66.609 68.1048 66.6196Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M112 66.5C112 65.6716 112.672 65 113.5 65C114.328 65 115 65.6716 115 66.5V73H112V66.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M121.417 67.8786L136.105 66.6196C136.229 66.609 136.226 66.4272 136.102 66.4201L120.951 65.5543C120.319 65.5182 119.686 65.5572 119.063 65.6703L114.5 66.5L118.628 67.6259C119.536 67.8734 120.48 67.9589 121.417 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M105.083 67.8786L90.3952 66.6196C90.2715 66.609 90.2741 66.4272 90.398 66.4201L105.549 65.5543C106.181 65.5182 106.814 65.5572 107.437 65.6703L112 66.5L107.872 67.6259C106.964 67.8734 106.02 67.9589 105.083 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M112 66.5V73H115V66.5C115 65.6716 114.328 65 113.5 65C112.672 65 112 65.6716 112 66.5ZM112 66.5L107.872 67.6259C106.964 67.8734 106.02 67.9589 105.083 67.8786L90.3952 66.6196C90.2715 66.609 90.2741 66.4272 90.398 66.4201L105.549 65.5543C106.181 65.5182 106.814 65.5572 107.437 65.6703L112 66.5ZM136.105 66.6196L121.417 67.8786C120.48 67.9589 119.536 67.8734 118.628 67.6259L114.5 66.5L119.063 65.6703C119.686 65.5572 120.319 65.5182 120.951 65.5543L136.102 66.4201C136.226 66.4272 136.229 66.609 136.105 66.6196Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M65.1001 86.5311L68.0001 80H71.0001L67.2126 86.3124C66.7464 87.0895 66.5001 87.9787 66.5001 88.8849V95.0849C66.5001 95.5903 66.0904 96 65.585 96C65.0796 96 64.6699 95.5903 64.6699 95.0849V88.5601C64.6699 87.8612 64.8165 87.1699 65.1001 86.5311Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M94.9 86.5311L92.0001 80H89.0001L92.7875 86.3124C93.2538 87.0895 93.5001 87.9787 93.5001 88.8849V95.0849C93.5001 95.5903 93.9098 96 94.4151 96C94.9205 96 95.3302 95.5903 95.3302 95.0849V88.5601C95.3302 87.8612 95.1836 87.1699 94.9 86.5311Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M65.1001 86.5311L68.0001 80H71.0001L67.2126 86.3124C66.7464 87.0895 66.5001 87.9787 66.5001 88.8849V95.0849C66.5001 95.5903 66.0904 96 65.585 96C65.0796 96 64.6699 95.5903 64.6699 95.0849V88.5601C64.6699 87.8612 64.8165 87.1699 65.1001 86.5311Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M94.9 86.5311L92.0001 80H89.0001L92.7875 86.3124C93.2538 87.0895 93.5001 87.9787 93.5001 88.8849V95.0849C93.5001 95.5903 93.9098 96 94.4151 96C94.9205 96 95.3302 95.5903 95.3302 95.0849V88.5601C95.3302 87.8612 95.1836 87.1699 94.9 86.5311Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M92.5649 79.8671L119.363 73.562C119.736 73.4742 120 73.1411 120 72.7575C120 72.3291 119.673 71.9716 119.246 71.9342L90.4698 69.4121H70.604L40.6231 71.9476C40.2708 71.9774 40 72.2721 40 72.6257C40 72.9393 40.2143 73.2123 40.519 73.2867L67.4153 79.8572C67.8037 79.952 68.2021 80 68.6019 80H91.4197C91.8053 80 92.1895 79.9554 92.5649 79.8671Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="82" rx="6" ry="6" transform="rotate(90 80 82)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="82" rx="4" ry="4" transform="rotate(90 80 82)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="81" cy="81" rx="2" ry="2" transform="rotate(90 81 81)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var yi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M99 78C101.209 78 103 79.7909 103 82C103 84.2091 101.209 86 99 86V78Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M99 87V78L56 77L65.7024 87.6727C65.892 87.8811 66.1606 88 66.4424 88H98C98.5523 88 99 87.5523 99 87Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M44 66.5C44 65.6716 44.6716 65 45.5 65C46.3284 65 47 65.6716 47 66.5V73H44V66.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M53.4165 67.8786L68.1048 66.6196C68.2285 66.609 68.226 66.4272 68.102 66.4201L52.9506 65.5543C52.3191 65.5182 51.6855 65.5572 51.0632 65.6703L46.5 66.5L50.6284 67.6259C51.5357 67.8734 52.4795 67.9589 53.4165 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M37.0835 67.8786L22.3952 66.6196C22.2715 66.609 22.2741 66.4272 22.398 66.4201L37.5494 65.5543C38.1809 65.5182 38.8145 65.5572 39.4368 65.6703L44 66.5L39.8716 67.6259C38.9643 67.8734 38.0205 67.9589 37.0835 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M44 66.5V73H47V66.5C47 65.6716 46.3284 65 45.5 65C44.6716 65 44 65.6716 44 66.5ZM44 66.5L39.8716 67.6259C38.9643 67.8734 38.0205 67.9589 37.0835 67.8786L22.3952 66.6196C22.2715 66.609 22.2741 66.4272 22.398 66.4201L37.5494 65.5543C38.1809 65.5182 38.8145 65.5572 39.4368 65.6703L44 66.5ZM68.1048 66.6196L53.4165 67.8786C52.4795 67.9589 51.5357 67.8734 50.6284 67.6259L46.5 66.5L51.0632 65.6703C51.6855 65.5572 52.3191 65.5182 52.9506 65.5543L68.102 66.4201C68.226 66.4272 68.2285 66.609 68.1048 66.6196Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M112 66.5C112 65.6716 112.672 65 113.5 65C114.328 65 115 65.6716 115 66.5V73H112V66.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M121.417 67.8786L136.105 66.6196C136.229 66.609 136.226 66.4272 136.102 66.4201L120.951 65.5543C120.319 65.5182 119.686 65.5572 119.063 65.6703L114.5 66.5L118.628 67.6259C119.536 67.8734 120.48 67.9589 121.417 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M105.083 67.8786L90.3952 66.6196C90.2715 66.609 90.2741 66.4272 90.398 66.4201L105.549 65.5543C106.181 65.5182 106.814 65.5572 107.437 65.6703L112 66.5L107.872 67.6259C106.964 67.8734 106.02 67.9589 105.083 67.8786Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M112 66.5V73H115V66.5C115 65.6716 114.328 65 113.5 65C112.672 65 112 65.6716 112 66.5ZM112 66.5L107.872 67.6259C106.964 67.8734 106.02 67.9589 105.083 67.8786L90.3952 66.6196C90.2715 66.609 90.2741 66.4272 90.398 66.4201L105.549 65.5543C106.181 65.5182 106.814 65.5572 107.437 65.6703L112 66.5ZM136.105 66.6196L121.417 67.8786C120.48 67.9589 119.536 67.8734 118.628 67.6259L114.5 66.5L119.063 65.6703C119.686 65.5572 120.319 65.5182 120.951 65.5543L136.102 66.4201C136.226 66.4272 136.229 66.609 136.105 66.6196Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M92.5649 79.8671L119.363 73.562C119.736 73.4742 120 73.1411 120 72.7575C120 72.3291 119.673 71.9716 119.246 71.9342L90.4698 69.4121H70.604L40.6231 71.9476C40.2708 71.9774 40 72.2721 40 72.6257C40 72.9393 40.2143 73.2123 40.519 73.2867L67.4153 79.8572C67.8037 79.952 68.2021 80 68.6019 80H91.4197C91.8053 80 92.1895 79.9554 92.5649 79.8671Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M100.817 86.0114L92 80H88L99.3611 86.0863C100.986 86.9567 102 88.6505 102 90.4937V95.5C102 95.7761 102.224 96 102.5 96C102.776 96 103 95.7761 103 95.5V90.1425C103 88.4892 102.183 86.9428 100.817 86.0114Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M58 90.0902V95.5C58 95.7761 57.7761 96 57.5 96C57.2239 96 57 95.7761 57 95.5V89.7447C57 88.0352 57.8734 86.4442 59.3156 85.5264L66.7716 80.7817C67.5739 80.2712 68.5051 80 69.456 80H72L60.7639 85.618C59.07 86.465 58 88.1963 58 90.0902Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M100.817 86.0114L92 80H88L99.3611 86.0863C100.986 86.9567 102 88.6505 102 90.4937V95.5C102 95.7761 102.224 96 102.5 96C102.776 96 103 95.7761 103 95.5V90.1425C103 88.4892 102.183 86.9428 100.817 86.0114Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M58 90.0902V95.5C58 95.7761 57.7761 96 57.5 96C57.2239 96 57 95.7761 57 95.5V89.7447C57 88.0352 57.8734 86.4442 59.3156 85.5264L66.7716 80.7817C67.5739 80.2712 68.5051 80 69.456 80H72L60.7639 85.618C59.07 86.465 58 88.1963 58 90.0902Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var wi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="80" cy="61" rx="4" ry="4" transform="rotate(90 80 61)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M86 60C87.1046 60 88 60.8954 88 62L88 86C88 87.1046 87.1046 88 86 88L74 88C72.8954 88 72 87.1046 72 86L72 62C72 60.8954 72.8954 60 74 60L86 60Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M113.61 46.5204C113.678 46.429 113.565 46.3127 113.472 46.3788L92.0296 61.7523C89.9911 63.2139 87.5458 63.9999 85.0374 63.9999H73.9992C71.4028 63.9999 68.8764 63.1578 66.7993 61.6L46.5198 46.3906C46.4283 46.3221 46.3126 46.4353 46.3791 46.5283L61.7526 67.9705C63.2142 70.0091 64.0002 72.4544 64.0002 74.9627V85.0371C64.0002 87.5455 63.2142 89.9908 61.7526 92.0293L46.3791 113.472C46.3125 113.565 46.4283 113.679 46.5198 113.61L66.8002 98.3999C68.8774 96.8421 71.4038 95.9999 74.0002 95.9999H85.0373C87.5457 95.9999 89.9911 96.786 92.0297 98.2477L113.472 113.622C113.565 113.688 113.678 113.572 113.61 113.48L98.4002 93.2009C96.8423 91.1237 96.0002 88.5974 96.0002 86.001V73.999C96.0002 71.4025 96.8424 68.8761 98.4003 66.7989L113.61 46.5204Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M45.6232 41C44.5326 41 43.5232 41.3497 42.7013 41.9424L42.3039 41.5957C41.8708 41.2171 41.2951 41.0437 40.7248 41.1191L24.0129 43.334C23.2505 43.4352 22.613 43.9652 22.3742 44.6963L22.05 45.6895C21.8392 46.3356 22.3215 46.9997 23.0011 47H40.7238C41.1872 49.2821 43.2043 51 45.6232 51C46.7144 50.9999 47.7231 50.649 48.5451 50.0557L48.9406 50.4033C49.3738 50.7823 49.9501 50.9564 50.5207 50.8809L67.2316 48.665C67.9941 48.5639 68.6315 48.0339 68.8703 47.3027L69.1945 46.3096C69.4051 45.6635 68.9238 45.0004 68.2443 45H50.5226C50.0594 42.718 48.0419 41.0003 45.6232 41ZM43.8927 47C44.2387 47.5972 44.8834 48 45.6232 48C45.795 47.9999 45.9612 47.9754 46.1203 47.9346L47.7677 49.375C47.1479 49.7698 46.4126 49.9999 45.6232 50C43.7593 50 42.1922 48.7253 41.7482 47H43.8927ZM45.6232 42C47.4868 42.0003 49.0533 43.2749 49.4972 45H47.3527C47.0068 44.403 46.3628 44.0002 45.6232 44C45.4516 44 45.2851 44.0238 45.1261 44.0645L43.4797 42.623C44.0992 42.2291 44.8346 42 45.6232 42Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M40.1992 91.1499C39.5205 91.1136 39.0039 91.7511 39.1797 92.4077L43.7666 109.526C41.6821 110.564 40.545 112.957 41.1709 115.293C41.4534 116.348 42.0529 117.232 42.8389 117.873L42.6055 118.344C42.3516 118.861 42.3331 119.462 42.5537 119.994L49.0185 135.562C49.3136 136.272 49.9907 136.751 50.7588 136.792L51.8017 136.848C52.4803 136.884 52.9969 136.248 52.8213 135.591L48.2344 118.473C50.3187 117.435 51.4559 115.042 50.8301 112.706C50.5478 111.652 49.9491 110.768 49.1641 110.127L49.3955 109.654C49.6491 109.137 49.6678 108.537 49.4473 108.005L42.9824 92.4361C42.6873 91.7258 42.0101 91.247 41.2422 91.2056L40.1992 91.1499ZM48.708 111.056C49.2486 111.553 49.6602 112.203 49.8642 112.964C50.3464 114.765 49.5201 116.608 47.9687 117.483L47.4141 115.412C47.9013 114.923 48.123 114.196 47.9316 113.482C47.8872 113.316 47.8217 113.161 47.7412 113.018L48.708 111.056ZM44.5859 112.586C44.0986 113.075 43.877 113.802 44.0683 114.517C44.1129 114.683 44.18 114.838 44.2607 114.981L43.2949 116.944C42.7534 116.447 42.341 115.797 42.1367 115.035C41.6545 113.235 42.4799 111.392 44.0312 110.516L44.5859 112.586Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M96.6179 32.8858C95.9071 32.5923 95.0906 32.7324 94.5183 33.2461L93.7409 33.9444C93.2354 34.3986 93.3203 35.2148 93.9089 35.5547L109.257 44.4151C108.517 46.6231 109.405 49.1196 111.5 50.3291C112.445 50.8748 113.494 51.0755 114.503 50.9727L114.672 51.4717C114.857 52.0166 115.269 52.455 115.801 52.6748L131.382 59.1114C132.092 59.405 132.909 59.2648 133.481 58.751L134.26 58.0528C134.764 57.5984 134.679 56.7843 134.091 56.4444L118.743 47.583C119.483 45.375 118.594 42.8785 116.5 41.669C115.555 41.1238 114.507 40.9221 113.499 41.0244L113.328 40.5254C113.142 39.981 112.731 39.5431 112.199 39.3233L96.6179 32.8858ZM112.001 46C112.002 46.6902 112.359 47.3615 113 47.7315C113.149 47.8175 113.305 47.8796 113.464 47.9239L114.17 49.9942C113.435 50.026 112.683 49.8576 112 49.4629C110.386 48.531 109.666 46.6438 110.144 44.9278L112.001 46ZM113.833 42.003C114.566 41.9716 115.317 42.141 116 42.5352C117.614 43.4671 118.332 45.3543 117.854 47.0703L115.998 45.9981C115.997 45.3079 115.64 44.6366 115 44.2666C114.851 44.1808 114.695 44.1185 114.537 44.0743L113.833 42.003Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M134.569 102.481C134.429 101.816 133.68 101.482 133.091 101.822L117.743 110.683C116.201 108.938 113.595 108.459 111.5 109.668C110.555 110.214 109.856 111.022 109.441 111.947L108.925 111.844C108.36 111.732 107.774 111.87 107.318 112.221L93.9533 122.495C93.3435 122.964 93.0562 123.741 93.215 124.494L93.4308 125.516C93.5715 126.181 94.3207 126.515 94.9093 126.176L110.257 117.314C111.799 119.059 114.405 119.537 116.5 118.328C117.444 117.783 118.143 116.976 118.559 116.052L119.076 116.153C119.641 116.265 120.226 116.127 120.682 115.776L134.047 105.503C134.657 105.034 134.944 104.255 134.785 103.503L134.569 102.481ZM117.544 115.851C117.205 116.502 116.683 117.069 116 117.463C114.386 118.395 112.392 118.074 111.145 116.802L113.001 115.729C113.599 116.074 114.359 116.1 115 115.73C115.149 115.644 115.281 115.54 115.399 115.426L117.544 115.851ZM112 110.534C113.614 109.602 115.608 109.923 116.856 111.195L114.999 112.267C114.401 111.923 113.641 111.897 113 112.266C112.851 112.353 112.719 112.457 112.602 112.572L110.455 112.147C110.795 111.496 111.317 110.929 112 110.534Z" fill="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Li=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M121.033 100.2L101 80H96L118.289 99.8667C118.741 100.27 119 100.846 119 101.452V102.835C119 103.478 119.522 104 120.165 104C120.809 104 121.33 103.478 121.33 102.835V100.922C121.33 100.652 121.223 100.392 121.033 100.2Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M39.2975 100.2L59.3301 80H64.3301L42.0407 99.8667C41.5887 100.27 41.3301 100.846 41.3301 101.452V102.835C41.3301 103.478 40.8085 104 40.1651 104C39.5216 104 39 103.478 39 102.835V100.922C39 100.652 39.1069 100.392 39.2975 100.2Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M121.033 100.2L101 80H96L118.289 99.8667C118.741 100.27 119 100.846 119 101.452V102.835C119 103.478 119.522 104 120.165 104C120.809 104 121.33 103.478 121.33 102.835V100.922C121.33 100.652 121.223 100.392 121.033 100.2Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M39.2975 100.2L59.3301 80H64.3301L42.0407 99.8667C41.5887 100.27 41.3301 100.846 41.3301 101.452V102.835C41.3301 103.478 40.8085 104 40.1651 104C39.5216 104 39 103.478 39 102.835V100.922C39 100.652 39.1069 100.392 39.2975 100.2Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M118 64H126V77.8755C126 79.2677 125.637 80.6358 124.946 81.8446L123.736 83.9611C122.969 85.3048 121.031 85.3048 120.264 83.9611L119.054 81.8446C118.363 80.6358 118 79.2677 118 77.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M34 64H42V77.8755C42 79.2677 41.6367 80.6358 40.9459 81.8446L39.7365 83.9611C38.9687 85.3048 37.0313 85.3048 36.2635 83.9611L35.0541 81.8446C34.3633 80.6358 34 79.2677 34 77.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M134 75.1317V73H120H98L90 79.9999L132.136 77.127C133.185 77.0555 134 76.1834 134 75.1317Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M26 75.1346V73H40H62L69 79.9999L27.8608 77.1298C26.8128 77.0567 26 76.1852 26 75.1346Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M93.039 84.5757L97.8895 73.2577C97.9624 73.0877 98 72.9046 98 72.7196V70.8904C98 69.6891 97.4814 68.5462 96.5773 67.7552C92.3372 64.045 86.8945 62 81.2603 62H78.8149C73.1357 62 67.653 64.0794 63.4022 67.8456C62.5105 68.6356 62 69.7699 62 70.9613V73L66.961 84.5757C67.5913 86.0464 69.0375 87 70.6376 87H89.3624C90.9625 87 92.4087 86.0464 93.039 84.5757Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="12.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="96.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="79" rx="6" ry="6" transform="rotate(90 80 79)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80" cy="79" rx="4" ry="4" transform="rotate(90 80 79)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="81" cy="78" rx="2" ry="2" transform="rotate(90 81 78)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var ki=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M131 75C133.209 75 135 76.7909 135 79C135 81.2091 133.209 83 131 83V75Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M132 84V74C132 73.4477 131.552 73 131 73H89L98.7002 84.6402C98.8901 84.8682 99.1716 85 99.4684 85H131C131.552 85 132 84.5523 132 84Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M129.736 73.4611L122.576 85.9923C122.22 86.6154 121.557 87 120.839 87H69.8301C69.2805 87 68.7346 86.9094 68.2144 86.7317L28 73V68.0879L29.1795 65.9233C30.0014 64.415 31.5399 63.4342 33.2542 63.3257L70 61H90L124.906 65.3632C125.627 65.4533 126.319 65.6995 126.935 66.0846L129.925 67.9534C129.972 67.9824 130 68.0332 130 68.0879V72.4689C130 72.8169 129.909 73.159 129.736 73.4611Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M28 68.0879V73L68.2144 86.7317C68.7346 86.9094 69.2805 87 69.8301 87H120.839C121.557 87 122.22 86.6154 122.576 85.9923L129.736 73.4611C129.909 73.159 130 72.8169 130 72.4689V68.0879M28 68.0879L29.1795 65.9233C30.0014 64.415 31.5399 63.4342 33.2542 63.3257L70 61H90L124.906 65.3632C125.627 65.4533 126.319 65.6995 126.935 66.0846L129.925 67.9534C129.972 67.9824 130 68.0332 130 68.0879M28 68.0879H130" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M128.918 100.202L101 80H96L126.097 99.9027C126.661 100.276 127 100.907 127 101.583V102.835C127 103.478 127.522 104 128.165 104C128.809 104 129.33 103.478 129.33 102.835V101.009C129.33 100.689 129.177 100.389 128.918 100.202Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M31.4125 100.202L58.3301 80H63.3301L34.2334 99.9027C33.6694 100.276 33.3301 100.907 33.3301 101.583V102.835C33.3301 103.478 32.8085 104 32.1651 104C31.5216 104 31 103.478 31 102.835V101.009C31 100.689 31.1534 100.389 31.4125 100.202Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M128.918 100.202L101 80H96L126.097 99.9027C126.661 100.276 127 100.907 127 101.583V102.835C127 103.478 127.522 104 128.165 104C128.809 104 129.33 103.478 129.33 102.835V101.009C129.33 100.689 129.177 100.389 128.918 100.202Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M31.4125 100.202L58.3301 80H63.3301L34.2334 99.9027C33.6694 100.276 33.3301 100.907 33.3301 101.583V102.835C33.3301 103.478 32.8085 104 32.1651 104C31.5216 104 31 103.478 31 102.835V101.009C31 100.689 31.1534 100.389 31.4125 100.202Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M118 64H126V73.8755C126 75.2677 125.637 76.6358 124.946 77.8446L123.736 79.9611C122.969 81.3048 121.031 81.3048 120.264 79.9611L119.054 77.8446C118.363 76.6358 118 75.2677 118 73.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M34 64H42V73.8755C42 75.2677 41.6367 76.6358 40.9459 77.8446L39.7365 79.9611C38.9687 81.3048 37.0313 81.3048 36.2635 79.9611L35.0541 77.8446C34.3633 76.6358 34 75.2677 34 73.8755V64Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M127 75.1735V74C127 73.4477 126.552 73 126 73H120H98.5803C98.2215 73 97.8901 73.1923 97.7121 73.5039L94.9519 78.3342C94.5507 79.0363 95.1053 79.8995 95.9106 79.8263L125.181 77.1653C126.211 77.0717 127 76.2079 127 75.1735Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M32 75.1735V74C32 73.4477 32.4477 73 33 73H40H61.3406C61.7406 73 62.1022 73.2384 62.2598 73.6061L64.3393 78.4583C64.6376 79.1544 64.0839 79.9167 63.3296 79.8481L33.8189 77.1653C32.7888 77.0717 32 76.2079 32 75.1735Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="12.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="96.5" y="57.5" width="51" height="7" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Mi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="80" cy="25" rx="4" ry="4" transform="rotate(90 80 25)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M87.5 26L87.5 50C87.5 50.8284 86.8284 51.5 86 51.5L74 51.5C73.1716 51.5 72.5 50.8284 72.5 50L72.5 26C72.5 25.1716 73.1716 24.5 74 24.5L86 24.5C86.8284 24.5 87.5 25.1716 87.5 26Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<g clip-path="url(#clip0_30829_50593)">
<path d="M74.124 68.9067L34.8998 38.5288C34.1757 37.968 33.974 36.9602 34.4265 36.164C34.8921 35.3447 35.9013 35.0093 36.7647 35.387L81.9764 55.1651C82.5202 55.403 82.7383 56.0593 82.4451 56.5754L75.6058 68.6102C75.305 69.1394 74.6053 69.2794 74.124 68.9067Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.124 91.0923L34.8998 121.47C34.1757 122.031 33.974 123.039 34.4265 123.835C34.8921 124.654 35.9013 124.99 36.7647 124.612L81.9764 104.834C82.5202 104.596 82.7383 103.94 82.4451 103.424L75.6058 91.3888C75.305 90.8597 74.6053 90.7196 74.124 91.0923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8757 68.9067L125.1 38.5288C125.824 37.968 126.026 36.9602 125.573 36.164C125.108 35.3447 124.098 35.0093 123.235 35.387L78.0233 55.1651C77.4795 55.403 77.2614 56.0593 77.5546 56.5754L84.394 68.6102C84.6947 69.1394 85.3945 69.2794 85.8757 68.9067Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8757 91.0923L125.1 121.47C125.824 122.031 126.026 123.039 125.573 123.835C125.108 124.654 124.098 124.99 123.235 124.612L78.0233 104.834C77.4795 104.596 77.2614 103.94 77.5546 103.424L84.394 91.3889C84.6947 90.8597 85.3945 90.7196 85.8757 91.0923Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.124 68.9067L34.8998 38.5288C34.1757 37.968 33.974 36.9602 34.4265 36.164C34.8921 35.3447 35.9013 35.0093 36.7647 35.387L81.9764 55.1651C82.5202 55.403 82.7383 56.0593 82.4451 56.5754L75.6058 68.6102C75.305 69.1394 74.6053 69.2794 74.124 68.9067Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74.124 91.0923L34.8998 121.47C34.1757 122.031 33.974 123.039 34.4265 123.835C34.8921 124.654 35.9013 124.99 36.7647 124.612L81.9764 104.834C82.5202 104.596 82.7383 103.94 82.4451 103.424L75.6058 91.3888C75.305 90.8597 74.6053 90.7196 74.124 91.0923Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.8757 68.9067L125.1 38.5288C125.824 37.968 126.026 36.9602 125.573 36.164C125.108 35.3447 124.098 35.0093 123.235 35.387L78.0233 55.1651C77.4795 55.403 77.2614 56.0593 77.5546 56.5754L84.394 68.6102C84.6947 69.1394 85.3945 69.2794 85.8757 68.9067Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.8757 91.0923L125.1 121.47C125.824 122.031 126.026 123.039 125.573 123.835C125.108 124.654 124.098 124.99 123.235 124.612L78.0233 104.834C77.4795 104.596 77.2614 103.94 77.5546 103.424L84.394 91.3889C84.6947 90.8597 85.3945 90.7196 85.8757 91.0923Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M68.6243 31.3047C68.9292 29.3933 70.431 28 72.1856 28H87.8144C89.569 28 91.0707 29.3933 91.3757 31.3047L92.8953 40.8301C94.9619 53.7844 96 66.8819 96 80C96 93.1181 94.9619 106.216 92.8953 119.17L91.3757 128.695C91.0707 130.607 89.569 132 87.8144 132H72.1856C70.431 132 68.9292 130.607 68.6243 128.695L67.1047 119.17C65.0381 106.216 64 93.1181 64 80C64 66.8819 65.0381 53.7844 67.1047 40.8301L68.6243 31.3047Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M23.4682 106.879C22.8625 107.187 22.7343 107.997 23.2148 108.477L34.2813 119.544C33.9279 120.078 33.6995 120.671 33.6004 121.281L33.2282 121.307C32.6539 121.345 32.1234 121.629 31.7733 122.086L22.7805 133.829C22.313 134.439 22.2372 135.264 22.585 135.949L22.8771 136.525C23.185 137.131 23.9943 137.259 24.475 136.779L35.5381 125.716C36.0735 126.071 36.669 126.297 37.281 126.397L37.3058 126.767C37.3442 127.341 37.6284 127.872 38.0855 128.222L49.8273 137.215C50.4379 137.683 51.2628 137.758 51.9486 137.41L52.5231 137.119C53.1293 136.811 53.2587 136.001 52.7779 135.52L41.7128 124.455C42.0676 123.919 42.2974 123.325 42.3965 122.713L42.7666 122.69C43.341 122.651 43.8715 122.367 44.2215 121.91L53.2144 110.168C53.6818 109.557 53.7585 108.732 53.4105 108.046L53.1184 107.471C52.8104 106.865 51.9998 106.737 51.5191 107.217L40.4561 118.28C39.9199 117.925 39.3238 117.697 38.7111 117.599L38.6869 117.23C38.6485 116.656 38.3643 116.126 37.9073 115.776L26.1648 106.783C25.5541 106.315 24.7293 106.238 24.0434 106.587L23.4682 106.879Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="37.9998" cy="122" r="2" transform="rotate(-45 37.9998 122)" fill="var(--container-background-color)"/>
<path d="M19.2617 103.262C8.91278 113.611 8.91278 130.39 19.2617 140.738C29.6106 151.087 46.3894 151.087 56.7383 140.738C67.0872 130.39 67.0872 113.611 56.7383 103.262C46.3894 92.9129 29.6106 92.9129 19.2617 103.262ZM22.0901 106.09C30.8769 97.3034 45.1231 97.3034 53.9099 106.09C62.6967 114.877 62.6967 129.123 53.9099 137.91C45.1231 146.697 30.8769 146.697 22.0901 137.91C13.3033 129.123 13.3033 114.877 22.0901 106.09Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M19.2617 103.262L19.6152 103.615C9.46159 113.769 9.46159 130.231 19.6152 140.385L19.2617 140.738L18.9081 141.092C8.36396 130.548 8.36396 113.452 18.9081 102.908L19.2617 103.262ZM19.2617 140.738L19.6152 140.385C29.7689 150.539 46.2311 150.539 56.3848 140.385L56.7383 140.738L57.0919 141.092C46.5477 151.636 29.4523 151.636 18.9081 141.092L19.2617 140.738ZM56.7383 140.738L56.3848 140.385C66.5384 130.231 66.5384 113.769 56.3848 103.615L56.7383 103.262L57.0919 102.908C67.636 113.452 67.636 130.548 57.0919 141.092L56.7383 140.738ZM56.7383 103.262L56.3848 103.615C46.2311 93.4617 29.7689 93.4617 19.6152 103.615L19.2617 103.262L18.9081 102.908C29.4523 92.3641 46.5477 92.3641 57.0919 102.908L56.7383 103.262ZM22.0901 106.09L21.7365 105.737C30.7186 96.7546 45.2814 96.7546 54.2635 105.737L53.9099 106.09L53.5563 106.444C44.9648 97.8522 31.0352 97.8522 22.4437 106.444L22.0901 106.09ZM53.9099 106.09L54.2635 105.737C63.2455 114.719 63.2455 129.281 54.2635 138.264L53.9099 137.91L53.5563 137.556C62.1479 128.965 62.1479 115.035 53.5563 106.444L53.9099 106.09ZM53.9099 137.91L54.2635 138.264C45.2814 147.246 30.7186 147.246 21.7365 138.264L22.0901 137.91L22.4437 137.556C31.0352 146.148 44.9648 146.148 53.5563 137.556L53.9099 137.91ZM22.0901 137.91L21.7365 138.264C12.7545 129.281 12.7545 114.719 21.7365 105.737L22.0901 106.09L22.4437 106.444C13.8521 115.035 13.8521 128.965 22.4437 137.556L22.0901 137.91Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M38.4178 17.0324C37.7716 16.8217 37.1075 17.303 37.1072 17.9826V33.634C36.4794 33.7621 35.8989 34.0194 35.3973 34.3811L35.116 34.136C34.6827 33.757 34.1066 33.5828 33.5359 33.6584L18.8748 35.6028C18.1124 35.7038 17.475 36.233 17.2361 36.9641L17.0359 37.5774C16.825 38.2236 17.3064 38.8877 17.9861 38.8879H33.6336C33.7611 39.5168 34.0227 40.0964 34.3846 40.5988L34.1385 40.8801C33.7596 41.3134 33.5853 41.8896 33.6609 42.4602L35.6053 57.1213C35.7064 57.8837 36.2357 58.5211 36.9666 58.76L37.5799 58.9602C38.2261 59.171 38.8902 58.6896 38.8904 58.01V42.3615C39.5198 42.2336 40.1016 41.9762 40.6043 41.6135L40.8836 41.8586C41.3168 42.2376 41.8921 42.4117 42.4627 42.3362L57.1248 40.3918C57.8873 40.2907 58.5247 39.7617 58.7635 39.0305L58.9637 38.4172C59.1743 37.7711 58.6931 37.1079 58.0135 37.1076H42.367C42.2391 36.4769 41.9785 35.8942 41.615 35.3908L41.8582 35.1125C42.2372 34.6793 42.4113 34.104 42.3357 33.5334L40.3924 18.8713C40.2913 18.1088 39.7613 17.4714 39.0301 17.2326L38.4178 17.0324Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="38" cy="38" r="2" fill="var(--container-background-color)"/>
<path d="M38 11.5C23.3645 11.5 11.5 23.3645 11.5 38C11.5 52.6355 23.3645 64.5 38 64.5C52.6355 64.5 64.5 52.6355 64.5 38C64.5 23.3645 52.6355 11.5 38 11.5ZM38 15.5C50.4264 15.5 60.5 25.5736 60.5 38C60.5 50.4264 50.4264 60.5 38 60.5C25.5736 60.5 15.5 50.4264 15.5 38C15.5 25.5736 25.5736 15.5 38 15.5Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M38 11.5V12C23.6406 12 12 23.6406 12 38H11.5H11C11 23.0883 23.0883 11 38 11V11.5ZM11.5 38H12C12 52.3594 23.6406 64 38 64V64.5V65C23.0883 65 11 52.9117 11 38H11.5ZM38 64.5V64C52.3594 64 64 52.3594 64 38H64.5H65C65 52.9117 52.9117 65 38 65V64.5ZM64.5 38H64C64 23.6406 52.3594 12 38 12V11.5V11C52.9117 11 65 23.0883 65 38H64.5ZM38 15.5V15C50.7025 15 61 25.2975 61 38H60.5H60C60 25.8497 50.1503 16 38 16V15.5ZM60.5 38H61C61 50.7025 50.7025 61 38 61V60.5V60C50.1503 60 60 50.1503 60 38H60.5ZM38 60.5V61C25.2975 61 15 50.7025 15 38H15.5H16C16 50.1503 25.8497 60 38 60V60.5ZM15.5 38H15C15 25.2975 25.2975 15 38 15V15.5V16C25.8497 16 16 25.8497 16 38H15.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M111.878 103.633C111.213 103.773 110.879 104.522 111.219 105.111L119.044 118.665C118.565 119.09 118.191 119.603 117.937 120.167L117.571 120.095C117.006 119.983 116.42 120.121 115.964 120.472L104.238 129.486C103.629 129.955 103.342 130.732 103.5 131.484L103.634 132.115C103.774 132.781 104.523 133.114 105.111 132.774L118.661 124.952C119.086 125.433 119.603 125.806 120.168 126.06L120.096 126.424C119.985 126.989 120.122 127.575 120.473 128.032L129.487 139.758C129.956 140.367 130.733 140.653 131.485 140.495L132.116 140.362C132.781 140.222 133.116 139.473 132.776 138.884L124.951 125.332C125.433 124.906 125.808 124.392 126.063 123.827L126.426 123.9C126.991 124.011 127.577 123.874 128.033 123.523L139.759 114.508C140.368 114.04 140.656 113.263 140.497 112.51L140.364 111.879C140.223 111.214 139.474 110.88 138.885 111.22L125.336 119.042C124.91 118.56 124.393 118.186 123.827 117.932L123.898 117.571C124.01 117.006 123.873 116.42 123.522 115.963L114.507 104.238C114.038 103.628 113.261 103.341 112.509 103.499L111.878 103.633Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="122" cy="122.002" r="2" transform="rotate(-30 122 122.002)" fill="var(--container-background-color)"/>
<path d="M108.751 99.0508C96.0758 106.369 91.7331 122.576 99.0508 135.25C106.369 147.925 122.576 152.268 135.251 144.95C147.925 137.632 152.268 121.425 144.95 108.75C137.632 96.0757 121.425 91.733 108.751 99.0508ZM110.751 102.515C121.512 96.3017 135.273 99.9889 141.486 110.75C147.699 121.512 144.012 135.273 133.251 141.486C122.489 147.699 108.728 144.012 102.515 133.25C96.3017 122.489 99.9889 108.728 110.751 102.515Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M108.751 99.0508L109.001 99.4838C96.5649 106.663 92.3042 122.565 99.4839 135L99.0508 135.25L98.6178 135.5C91.162 122.587 95.5866 106.074 108.501 98.6178L108.751 99.0508ZM99.0508 135.25L99.4839 135C106.664 147.436 122.565 151.697 135.001 144.517L135.251 144.95L135.501 145.383C122.587 152.839 106.074 148.414 98.6178 135.5L99.0508 135.25ZM135.251 144.95L135.001 144.517C147.436 137.337 151.697 121.436 144.517 109L144.95 108.75L145.383 108.5C152.839 121.414 148.414 137.927 135.501 145.383L135.251 144.95ZM144.95 108.75L144.517 109C137.337 96.5648 121.436 92.3041 109.001 99.4838L108.751 99.0508L108.501 98.6178C121.414 91.1619 137.927 95.5866 145.383 108.5L144.95 108.75ZM110.751 102.515L110.501 102.082C121.501 95.7306 135.568 99.4997 141.919 110.5L141.486 110.75L141.053 111C134.978 100.478 121.523 96.8728 111.001 102.948L110.751 102.515ZM141.486 110.75L141.919 110.5C148.27 121.501 144.501 135.568 133.501 141.919L133.251 141.486L133.001 141.053C143.523 134.978 147.128 121.523 141.053 111L141.486 110.75ZM133.251 141.486L133.501 141.919C122.5 148.27 108.433 144.501 102.082 133.5L102.515 133.25L102.948 133C109.023 143.523 122.478 147.128 133.001 141.053L133.251 141.486ZM102.515 133.25L102.082 133.5C95.7307 122.5 99.4998 108.433 110.501 102.082L110.751 102.515L111.001 102.948C100.478 109.023 96.8728 122.478 102.948 133L102.515 133.25Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M132.845 20.0475C132.391 19.5422 131.575 19.6279 131.236 20.2165L123.41 33.7701C122.803 33.5671 122.171 33.4998 121.556 33.5621L121.435 33.2092C121.249 32.6644 120.837 32.2255 120.305 32.0056L106.635 26.3584C105.925 26.0649 105.109 26.205 104.536 26.7185L104.056 27.1495C103.551 27.6038 103.636 28.4188 104.225 28.7588L117.774 36.5815C117.569 37.1906 117.505 37.8244 117.567 38.4413L117.216 38.5611C116.671 38.7468 116.233 39.1586 116.013 39.6907L110.365 53.3601C110.071 54.0709 110.212 54.8872 110.726 55.4596L111.156 55.9391C111.61 56.4449 112.426 56.3603 112.766 55.7715L120.59 42.2195C121.199 42.4235 121.832 42.4919 122.449 42.4291L122.568 42.7806C122.753 43.3254 123.165 43.7643 123.697 43.9842L137.367 49.6314C138.078 49.9248 138.895 49.7854 139.467 49.2718L139.947 48.8407C140.452 48.3865 140.367 47.5702 139.779 47.2302L126.229 39.4074C126.433 38.7976 126.499 38.1629 126.436 37.5455L126.785 37.4269C127.33 37.2412 127.769 36.8293 127.989 36.2973L133.636 22.6274C133.93 21.9165 133.79 21.0999 133.276 20.5276L132.845 20.0475Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="122" cy="37.9996" r="2" transform="rotate(30 122 37.9996)" fill="var(--container-background-color)"/>
<path d="M135.251 15.0488C122.576 7.73106 106.369 12.0737 99.0508 24.7485C91.7331 37.4233 96.0758 53.6304 108.751 60.9482C121.425 68.2659 137.632 63.9233 144.95 51.2485C152.268 38.5737 147.925 22.3666 135.251 15.0488ZM133.251 18.5129C144.012 24.7261 147.699 38.4869 141.486 49.2485C135.273 60.0101 121.512 63.6973 110.751 57.4841C99.9889 51.2709 96.3017 37.5101 102.515 26.7485C108.728 15.9869 122.489 12.2997 133.251 18.5129Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M135.251 15.0488L135.001 15.4818C122.565 8.30214 106.664 12.5629 99.4839 24.9985L99.0508 24.7485L98.6178 24.4985C106.074 11.5846 122.587 7.15997 135.501 14.6158L135.251 15.0488ZM99.0508 24.7485L99.4839 24.9985C92.3042 37.4341 96.5649 53.3355 109.001 60.5152L108.751 60.9482L108.501 61.3812C95.5866 53.9253 91.162 37.4124 98.6178 24.4985L99.0508 24.7485ZM108.751 60.9482L109.001 60.5152C121.436 67.6949 137.337 63.4341 144.517 50.9985L144.95 51.2485L145.383 51.4985C137.927 64.4124 121.414 68.837 108.501 61.3812L108.751 60.9482ZM144.95 51.2485L144.517 50.9985C151.697 38.5629 147.436 22.6615 135.001 15.4818L135.251 15.0488L135.501 14.6158C148.414 22.0717 152.839 38.5846 145.383 51.4985L144.95 51.2485ZM133.251 18.5129L133.501 18.0799C144.501 24.4312 148.27 38.4978 141.919 49.4985L141.486 49.2485L141.053 48.9985C147.128 38.4761 143.523 25.0211 133.001 18.9459L133.251 18.5129ZM141.486 49.2485L141.919 49.4985C135.568 60.4992 121.501 64.2684 110.501 57.9171L110.751 57.4841L111.001 57.0511C121.523 63.1262 134.978 59.5209 141.053 48.9985L141.486 49.2485ZM110.751 57.4841L110.501 57.9171C99.4998 51.5658 95.7307 37.4992 102.082 26.4985L102.515 26.7485L102.948 26.9985C96.8728 37.5209 100.478 50.9759 111.001 57.0511L110.751 57.4841ZM102.515 26.7485L102.082 26.4985C108.433 15.4978 122.5 11.7286 133.501 18.0799L133.251 18.5129L133.001 18.9459C122.478 12.8708 109.023 16.4761 102.948 26.9985L102.515 26.7485Z" fill="var(--instrument-tick-mark-secondary-color)"/>
</g>
<defs>
<clipPath id="clip0_30829_50593">
<rect width="160" height="160" fill="var(--instrument-frame-primary-color)" transform="matrix(-1 0 0 1 160 0)"/>
</clipPath>
</defs>
</svg>
`;var xi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M114.2 36.8008C118.177 36.8008 121.4 40.0243 121.4 44.0008V119.601C121.4 119.747 121.39 119.89 121.373 120.031C121.348 120.242 121.305 120.446 121.245 120.644C121.239 120.665 121.233 120.685 121.226 120.706C121.179 120.852 121.123 120.994 121.058 121.132C121.05 121.149 121.042 121.166 121.034 121.183C121.016 121.218 120.998 121.253 120.98 121.288C120.971 121.305 120.962 121.322 120.953 121.338C120.934 121.373 120.913 121.407 120.893 121.441C120.886 121.453 120.88 121.465 120.873 121.476C120.82 121.562 120.764 121.644 120.705 121.725C120.695 121.739 120.685 121.753 120.674 121.767C120.472 122.035 120.234 122.273 119.967 122.475C119.953 122.485 119.938 122.495 119.924 122.506C119.844 122.565 119.761 122.621 119.676 122.673C119.664 122.68 119.652 122.687 119.641 122.694C119.606 122.714 119.572 122.734 119.538 122.753C119.521 122.763 119.504 122.772 119.488 122.781C119.453 122.799 119.418 122.817 119.382 122.834C119.365 122.843 119.348 122.851 119.331 122.859C119.294 122.876 119.256 122.893 119.219 122.909C119.209 122.913 119.2 122.917 119.191 122.921C119.097 122.96 119.002 122.995 118.905 123.027C118.884 123.033 118.864 123.04 118.843 123.046C118.807 123.057 118.77 123.068 118.733 123.078C118.719 123.081 118.705 123.086 118.691 123.089C118.639 123.102 118.586 123.114 118.533 123.125C118.53 123.126 118.526 123.127 118.523 123.128C118.472 123.138 118.42 123.147 118.369 123.155C118.36 123.156 118.352 123.158 118.343 123.159C118.306 123.165 118.268 123.169 118.231 123.174C118.21 123.176 118.189 123.18 118.168 123.182L117.986 123.196L117.8 123.201H42.2001L42.0146 123.196C41.9318 123.192 41.8499 123.183 41.7686 123.174C41.7309 123.169 41.6933 123.165 41.6561 123.159C41.6475 123.158 41.6391 123.156 41.6306 123.155C41.5789 123.147 41.5276 123.138 41.4768 123.128C41.4732 123.127 41.4698 123.126 41.4662 123.125C41.4131 123.114 41.3603 123.102 41.308 123.089C41.2942 123.086 41.2805 123.081 41.2667 123.078C41.2295 123.068 41.1926 123.057 41.156 123.046C41.1354 123.04 41.1149 123.033 41.0944 123.027C40.9974 122.995 40.9021 122.96 40.8088 122.921C40.7993 122.917 40.7901 122.913 40.7807 122.909C40.7429 122.893 40.7053 122.876 40.6682 122.859C40.6511 122.851 40.6341 122.843 40.6172 122.834C40.5817 122.817 40.5465 122.799 40.5117 122.781C40.4949 122.772 40.4783 122.763 40.4616 122.753C40.4269 122.734 40.3928 122.714 40.3588 122.694C40.3472 122.687 40.3352 122.68 40.3236 122.673C40.2381 122.621 40.1555 122.565 40.0749 122.506C40.0609 122.495 40.0466 122.485 40.0327 122.475C39.7654 122.273 39.5271 122.035 39.3252 121.767C39.3147 121.753 39.3047 121.739 39.2944 121.725C39.2354 121.644 39.1789 121.562 39.1266 121.476C39.1195 121.465 39.1133 121.453 39.1063 121.441C39.0861 121.407 39.0658 121.373 39.0466 121.338C39.0374 121.322 39.0283 121.305 39.0193 121.288C39.0008 121.253 38.9831 121.218 38.9657 121.183C38.9574 121.166 38.9492 121.149 38.9411 121.132C38.8764 120.994 38.8204 120.852 38.7732 120.706C38.7667 120.685 38.7601 120.665 38.7539 120.644C38.6942 120.446 38.6515 120.242 38.6265 120.031C38.6096 119.89 38.6001 119.747 38.6001 119.601V44.0008C38.6001 40.0243 41.8236 36.8008 45.8001 36.8008H114.2ZM45.8001 40.4008C43.8741 40.4008 42.301 41.9133 42.2045 43.8153L42.2001 44.0008V116.001H117.8V44.0008C117.8 42.0126 116.188 40.4008 114.2 40.4008H45.8001Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<rect x="46.2998" y="81.4004" width="11.6" height="38.6" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="102.1" y="81.4004" width="11.6" height="38.6" rx="1.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M50.5 81.4004H53.7002C54.5285 81.4005 55.2002 82.072 55.2002 82.9004V98.4004H49V82.9004C49 82.072 49.6716 81.4004 50.5 81.4004Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M106.3 81.4004H109.5C110.328 81.4005 111 82.072 111 82.9004V98.4004H104.8V82.9004C104.8 82.072 105.471 81.4004 106.3 81.4004Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M36.7998 44.8008C36.7998 40.3825 40.3815 36.8008 44.7998 36.8008H115.2C119.618 36.8008 123.2 40.3825 123.2 44.8008V76.0008C123.2 78.2099 121.409 80.0008 119.2 80.0008H40.7998C38.5907 80.0008 36.7998 78.2099 36.7998 76.0008V44.8008Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M44 51.5996C44 49.3905 45.7909 47.5996 48 47.5996H112C114.209 47.5996 116 49.3905 116 51.5996V79.9996H44V51.5996Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M116 97.8994C116 98.4517 115.553 98.8994 115 98.8994H111.448C110.959 98.8994 110.542 98.5461 110.461 98.0639L110.194 96.4634C110.093 95.8538 110.563 95.2988 111.181 95.2988H113.038C113.591 95.2988 114.038 94.8511 114.038 94.2988V92.6992C114.038 92.1469 113.591 91.6992 113.038 91.6992H110.248C109.759 91.6992 109.342 91.3459 109.261 90.8638L108.994 89.2642C108.893 88.6546 109.363 88.0996 109.981 88.0996H115C115.553 88.0996 116 88.5473 116 89.0996V97.8994Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M60.1999 97.8994C60.1999 98.4517 59.7522 98.8994 59.1999 98.8994H55.6475C55.1588 98.8994 54.7416 98.5461 54.6612 98.0639L54.3942 96.4634C54.2925 95.8538 54.7626 95.2988 55.3806 95.2988H57.239C57.7913 95.2988 58.239 94.8511 58.239 94.2988V92.6992C58.239 92.1469 57.7913 91.6992 57.239 91.6992H54.4473C53.9585 91.6992 53.5414 91.3459 53.4609 90.8638L53.1941 89.2642C53.0924 88.6546 53.5624 88.0996 54.1804 88.0996H59.1999C59.7522 88.0996 60.1999 88.5473 60.1999 89.0996V97.8994Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M99.8005 97.8994C99.8005 98.4517 100.248 98.8994 100.801 98.8994H104.353C104.842 98.8994 105.259 98.5461 105.339 98.0639L105.606 96.4634C105.708 95.8538 105.238 95.2988 104.62 95.2988H102.599C102.047 95.2988 101.599 94.8511 101.599 94.2988V92.6992C101.599 92.1469 102.047 91.6992 102.599 91.6992H105.553C106.042 91.6992 106.459 91.3459 106.54 90.8638L106.806 89.2642C106.908 88.6546 106.438 88.0996 105.82 88.0996H100.801C100.248 88.0996 99.8005 88.5473 99.8005 89.0996V97.8994Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M44.0004 97.8994C44.0004 98.4517 44.4481 98.8994 45.0004 98.8994H48.5536C49.0425 98.8994 49.4597 98.5459 49.54 98.0637L49.8065 96.4631C49.908 95.8536 49.438 95.2988 48.8201 95.2988H46.8002C46.2479 95.2988 45.8002 94.8511 45.8002 94.2988V92.6992C45.8002 92.1469 46.2479 91.6992 46.8002 91.6992H49.7538C50.2427 91.6992 50.6599 91.3458 50.7402 90.8635L51.0067 89.2639C51.1082 88.6544 50.6382 88.0996 50.0203 88.0996H45.0004C44.4481 88.0996 44.0004 88.5473 44.0004 89.0996V97.8994Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="63.8008" r="9" transform="rotate(90 80 63.8008)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="79.9999" cy="63.8004" r="5.4" transform="rotate(90 79.9999 63.8004)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80.0002" cy="114.2" rx="7.2" ry="7.2" transform="rotate(90 80.0002 114.2)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="114.199" r="4.5" transform="rotate(90 80 114.199)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="49.4" cy="53.0004" rx="3.6" ry="3.6" transform="rotate(90 49.4 53.0004)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="110.6" cy="53.0004" rx="3.6" ry="3.6" transform="rotate(90 110.6 53.0004)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="102.5" cy="52.9992" rx="1.8" ry="1.8" transform="rotate(90 102.5 52.9992)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="80.9002" cy="61.9992" rx="1.8" ry="1.8" transform="rotate(90 80.9002 61.9992)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<ellipse cx="97.0999" cy="52.9992" rx="1.8" ry="1.8" transform="rotate(90 97.0999 52.9992)" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74.6001 20.5992C74.6001 17.6169 77.0178 15.1992 80.0001 15.1992C82.9824 15.1992 85.4001 17.6169 85.4001 20.5992V36.7992H74.6001V20.5992Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="76.3999" y="17" width="7.2" height="14.4" rx="3.6" fill="var(--instrument-frame-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Hi=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M120 115.55C120 108.343 114.157 102.5 106.95 102.5C99.7427 102.5 93.9 108.343 93.9 115.55V121.4H120V115.55Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="5.4" cy="5.4" r="5.4" transform="matrix(-1 0 0 1 135.3 58.4004)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M129.7 55.3008H108.5C107.672 55.3009 107 55.9724 107 56.8008V70.8008C107 71.6291 107.672 72.3007 108.5 72.3008H129.7C130.529 72.3008 131.2 71.6292 131.2 70.8008V56.8008C131.2 55.9724 130.529 55.3008 129.7 55.3008Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M134.562 97.8994C134.562 98.4517 135.01 98.8994 135.562 98.8994H142.715C143.204 98.8994 143.621 98.5461 143.702 98.0639L143.969 96.4634C144.07 95.8538 143.6 95.2988 142.982 95.2988H140.962C140.409 95.2988 139.962 94.8511 139.962 94.2988V92.6992C139.962 92.1469 140.409 91.6992 140.962 91.6992H143.915C144.404 91.6992 144.821 91.3459 144.902 90.8638L145.169 89.2642C145.27 88.6546 144.8 88.0996 144.182 88.0996H135.562C135.01 88.0996 134.562 88.5473 134.562 89.0996V97.8994Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M113.321 112.227L124.015 91.3626C125.394 88.6706 124.421 85.3695 121.801 83.857C119.182 82.3445 115.836 83.152 114.195 85.6929L101.473 105.386C99.3473 108.676 100.409 113.075 103.801 115.034C107.193 116.992 111.534 115.712 113.321 112.227Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M135.709 91.7969L120.522 85.7094C118.301 84.8189 115.8 86.0699 115.181 88.3818C114.561 90.6937 116.101 93.0274 118.47 93.367L134.666 95.6885C135.683 95.8342 136.648 95.1973 136.914 94.2053C137.18 93.2132 136.662 92.179 135.709 91.7969Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M22.803 119.6V79.9996M105.15 121.4L111 79.0996M70.95 79.0996L65.1 121.4" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4"/>
<path d="M110.057 85.9216L105.866 116.222C105.456 119.189 102.919 121.4 99.9227 121.4H71.9869C68.3464 121.4 65.5447 118.184 66.0435 114.578L70.2339 84.2776C70.6443 81.3098 73.1812 79.0996 76.1773 79.0996H104.113C107.754 79.0996 110.555 82.3154 110.057 85.9216Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4"/>
<path d="M65.5709 117.996L70.164 84.7846C70.5796 81.7794 68.2449 79.0996 65.2111 79.0996H35.7921C32.4899 79.0996 30.61 82.8747 32.5999 85.51L58.5167 119.832C59.2621 120.819 60.4273 121.4 61.6641 121.4C63.6336 121.4 65.3011 119.947 65.5709 117.996Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4"/>
<path d="M22.8032 115.4V82.4082C22.8032 80.5809 24.2845 79.0996 26.1118 79.0996C27.1494 79.0996 28.1269 79.5864 28.7522 80.4144L54.8597 114.989C56.8496 117.624 54.9697 121.4 51.6675 121.4H28.8032C25.4895 121.4 22.8032 118.713 22.8032 115.4Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4"/>
<path d="M128.655 48.8033L116.284 63.8634C115.351 64.9996 114.749 66.3712 114.544 67.8273L112.832 80.0008H21.2001C20.0955 80.0008 19.2001 79.1054 19.2001 78.0008V40.8008C19.2001 38.5916 20.991 36.8008 23.2001 36.8008H104.552C105.248 36.8008 105.941 36.8916 106.613 37.0709L126.595 42.3994C129.407 43.1492 130.502 46.5547 128.655 48.8033Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M101.999 79.9992C101.999 79.9992 102.265 51.1992 91.2 51.1992C80.1352 51.1992 80.4006 79.9992 80.4006 79.9992" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M130.8 121.4C130.8 120.405 129.994 119.6 129 119.6H20.9998V123.2H129C129.994 123.2 130.8 122.394 130.8 121.4Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M130.8 118C130.8 116.895 129.904 116 128.8 116H20.9998V121.2C20.9998 122.305 21.8952 123.2 22.9998 123.2H128.8C129.904 123.2 130.8 122.305 130.8 121.2V118Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<mask id="path-15-inside-1_25406_62344" fill="var(--instrument-frame-primary-color)">
<path fill-rule="evenodd" clip-rule="evenodd" d="M91.2002 51.1992C87.8899 51.1992 85.5945 53.7775 84.002 57.3906V57.5H98.4023V57.3994C96.8096 53.7817 94.5132 51.1993 91.2002 51.1992Z"/>
</mask>
<path fill-rule="evenodd" clip-rule="evenodd" d="M91.2002 51.1992C87.8899 51.1992 85.5945 53.7775 84.002 57.3906V57.5H98.4023V57.3994C96.8096 53.7817 94.5132 51.1993 91.2002 51.1992Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M91.2002 51.1992V50.1992H91.2002L91.2002 51.1992ZM84.002 57.3906H83.002V57.18L83.0869 56.9873L84.002 57.3906ZM84.002 57.5V58.5H83.002V57.5H84.002ZM98.4023 57.5H99.4023V58.5H98.4023V57.5ZM98.4023 57.3994L99.3176 56.9965L99.4023 57.189V57.3994H98.4023ZM91.2002 51.1992V52.1992C88.5179 52.1992 86.4709 54.2685 84.917 57.794L84.002 57.3906L83.0869 56.9873C84.7181 53.2864 87.2618 50.1992 91.2002 50.1992V51.1992ZM84.002 57.3906H85.002V57.5H84.002H83.002V57.3906H84.002ZM84.002 57.5V56.5H98.4023V57.5V58.5H84.002V57.5ZM98.4023 57.5H97.4023V57.3994H98.4023H99.4023V57.5H98.4023ZM98.4023 57.3994L97.4871 57.8023C95.9329 54.272 93.8846 52.1993 91.2002 52.1992L91.2002 51.1992L91.2002 50.1992C95.1417 50.1993 97.6864 53.2913 99.3176 56.9965L98.4023 57.3994Z" fill="var(--instrument-tick-mark-secondary-color)" mask="url(#path-15-inside-1_25406_62344)"/>
<path d="M91.1997 56.1992C89.2401 56.1992 87.4828 56.3987 86.23 56.7119C85.5997 56.8695 85.1248 57.0492 84.8198 57.2295C84.5739 57.3749 84.5174 57.4716 84.5044 57.499C84.5171 57.526 84.5728 57.6235 84.8198 57.7695C85.1248 57.9498 85.5997 58.1295 86.23 58.2871C87.4828 58.6003 89.2401 58.7988 91.1997 58.7988C93.1592 58.7988 94.9166 58.6003 96.1694 58.2871C96.7997 58.1296 97.2746 57.9498 97.5796 57.7695C97.8287 57.6223 97.8848 57.5251 97.897 57.499C97.8845 57.4724 97.8276 57.3761 97.5796 57.2295C97.2746 57.0492 96.7997 56.8695 96.1694 56.7119C94.9166 56.3987 93.1592 56.1992 91.1997 56.1992Z" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var $i=l`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="79.9999" cy="26.4996" r="5.4" transform="rotate(90 79.9999 26.4996)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M88.5 26.6992L88.5 47.8994C88.4999 48.7278 87.8284 49.3994 87 49.3994L73 49.3994C72.1716 49.3994 71.5001 48.7277 71.5 47.8994L71.5 26.6992C71.5 25.8708 72.1716 25.1992 73 25.1992L87 25.1992C87.8284 25.1992 88.5 25.8708 88.5 26.6992Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="36.7998" y="29.1992" width="86.4" height="111.6" rx="8" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="40.3999" y="54.4004" width="79.2" height="82.8" rx="6" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80.0002" cy="122.8" r="10.8" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.8419 122.491C88.6358 122.559 90.3391 125.593 88.9418 128.014C87.5331 130.453 84.0176 130.472 82.5829 128.047L81.4315 126.102C82.7073 125.548 83.5998 124.279 83.5998 122.799C83.5998 122.676 83.5934 122.555 83.5813 122.435L85.8419 122.491Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M76.4235 122.384C76.4079 122.52 76.3998 122.659 76.3998 122.799C76.3998 124.261 77.2714 125.517 78.5224 126.081L77.3464 128.009C75.8906 130.395 72.4116 130.353 71.0139 127.933C69.6052 125.493 71.346 122.439 74.163 122.409L76.4235 122.384Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80.0464 112.449C82.8632 112.45 84.6366 115.484 83.2544 117.939L82.1443 119.908C81.5453 119.463 80.8033 119.199 79.9998 119.199C79.2137 119.199 78.4868 119.452 77.8948 119.879L76.8129 117.895C75.4747 115.441 77.2512 112.449 80.0464 112.449Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M82.7 122.799C82.7 124.29 81.4912 125.499 80 125.499C78.5089 125.499 77.3 124.29 77.3 122.799C77.3 121.308 78.5089 120.099 80 120.099C81.4912 120.099 82.7 121.308 82.7 122.799Z" fill="var(--instrument-frame-primary-color)"/>
<circle cx="105.2" cy="68.8" r="10.8" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M111.042 68.4907C113.836 68.559 115.539 71.5933 114.141 74.0138C112.733 76.4535 109.217 76.4716 107.783 74.0472L106.631 72.1021C107.907 71.5485 108.8 70.2786 108.8 68.7992C108.8 68.6764 108.793 68.555 108.781 68.4354L111.042 68.4907Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M101.623 68.3844C101.608 68.5205 101.6 68.6589 101.6 68.7992C101.6 70.2605 102.471 71.5169 103.722 72.0811L102.546 74.0094C101.09 76.3954 97.6114 76.3532 96.2136 73.9329C94.805 71.4931 96.5457 68.4393 99.3627 68.409L101.623 68.3844Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M105.246 58.4492C108.063 58.4498 109.836 61.4843 108.454 63.9389L107.344 65.9076C106.745 65.4627 106.003 65.1992 105.2 65.1992C104.413 65.1993 103.687 65.4519 103.095 65.8795L102.013 63.8949C100.674 61.4411 102.451 58.4492 105.246 58.4492Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M107.9 68.7992C107.9 70.2904 106.691 71.4992 105.2 71.4992C103.709 71.4992 102.5 70.2904 102.5 68.7992C102.5 67.308 103.709 66.0992 105.2 66.0992C106.691 66.0992 107.9 67.308 107.9 68.7992Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M101.825 13L99.8 16.6L103.85 23.8L111.95 23.8L116 16.6L113.975 13" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4" stroke-linecap="round"/>
<path d="M46.0252 13L44.0002 16.6L48.0502 23.8L56.1502 23.8L60.2002 16.6L58.1752 13" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)" stroke-width="4" stroke-linecap="round"/>
<circle cx="54.8" cy="68.8" r="10.8" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M60.6417 68.4907C63.4356 68.559 65.1389 71.5933 63.7416 74.0138C62.3329 76.4535 58.8174 76.4716 57.3827 74.0472L56.2313 72.1021C57.5071 71.5485 58.3996 70.2786 58.3996 68.7992C58.3996 68.6764 58.3932 68.555 58.3811 68.4354L60.6417 68.4907Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M51.2233 68.3844C51.2077 68.5205 51.1996 68.6589 51.1996 68.7992C51.1996 70.2605 52.0712 71.5169 53.3222 72.0811L52.1462 74.0094C50.6904 76.3954 47.2115 76.3532 45.8137 73.9329C44.4051 71.4931 46.1458 68.4393 48.9628 68.409L51.2233 68.3844Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M54.8462 58.4492C57.663 58.4498 59.4364 61.4843 58.0542 63.9389L56.9441 65.9076C56.3451 65.4627 55.6031 65.1992 54.7996 65.1992C54.0135 65.1993 53.2867 65.4519 52.6946 65.8795L51.6127 63.8949C50.2745 61.4411 52.0511 58.4492 54.8462 58.4492Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M57.4998 68.7992C57.4998 70.2904 56.291 71.4992 54.7998 71.4992C53.3087 71.4992 52.0998 70.2904 52.0998 68.7992C52.0998 67.308 53.3087 66.0992 54.7998 66.0992C56.291 66.0992 57.4998 67.308 57.4998 68.7992Z" fill="var(--instrument-frame-primary-color)"/>
<rect x="100.7" y="23.8008" width="14.4" height="5.4" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="44.8999" y="23.8008" width="14.4" height="5.4" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="74.6001" y="76" width="10.8" height="28.8" rx="5.4" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="76.3999" y="77.8008" width="7.2" height="14.4" rx="3.6" fill="var(--instrument-frame-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var Pe=(t=>(t.none="none",t.small="small",t.medium="medium",t.large="large",t))(Pe||{}),Oe=(t=>(t.carFerryAft="car-ferry-aft",t.carFerrySide="car-ferry-side",t.carFerryTop="car-ferry-top",t.cargoFore="cargo-fore",t.cargoSide="cargo-side",t.cargoTop="cargo-top",t.cargoWindFore="cargo-wind-fore",t.cargoWindSide="cargo-wind-side",t.cargoWindTop="cargo-wind-top",t.fishingVesselSide="fishing-vessel-side",t.fishingVesselTop="fishing-vessel-top",t.foreFore="fore-fore",t.genericSide="generic-side",t.genericTop="generic-top",t.psvAft="psv-aft",t.psvFore="psv-fore",t.psvSide="psv-side",t.psvTop="psv-top",t.sovSide="sov-side",t.sovTop="sov-top",t.tankerFore="tanker-fore",t.tankerSide="tanker-side",t.tankerTop="tanker-top",t.usvLargeSide="usv-large-side",t.usvSmallSide="usv-small-side",t.droneMediumFront="drone-medium-front",t.droneMediumStbdSide="drone-medium-stbd-side",t.droneMediumTop="drone-medium-top",t.droneSmallFront="drone-small-front",t.droneSmallStbdSide="drone-small-stbd-side",t.droneSmallTop="drone-small-top",t.droneGenericFront="drone-generic-front",t.droneGenericSide="drone-generic-side",t.droneGenericTop="drone-generic-top",t.rovFront="rov-front",t.rovSide="rov-side",t.rovTop="rov-top",t))(Oe||{}),mr={"car-ferry-aft":U1,"car-ferry-side":W1,"car-ferry-top":G1,"cargo-fore":q1,"cargo-side":X1,"cargo-top":Y1,"cargo-wind-fore":J1,"cargo-wind-side":Q1,"cargo-wind-top":K1,"fishing-vessel-side":ei,"fishing-vessel-top":ti,"fore-fore":ri,"generic-side":oi,"generic-top":ii,"psv-aft":ai,"psv-fore":ni,"psv-side":si,"psv-top":li,"sov-side":ci,"sov-top":di,"tanker-fore":pi,"tanker-side":hi,"tanker-top":ui,"usv-large-side":vi,"usv-small-side":mi,"drone-medium-front":fi,"drone-medium-stbd-side":gi,"drone-medium-top":bi,"drone-small-front":Ci,"drone-small-stbd-side":yi,"drone-small-top":wi,"drone-generic-front":Li,"drone-generic-side":ki,"drone-generic-top":Mi,"rov-front":xi,"rov-side":Hi,"rov-top":$i};var Vi="important",ks=" !"+Vi,fr=qe(class extends De{constructor(t){if(super(t),t.type!==it.ATTRIBUTE||t.name!=="style"||t.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(t){return Object.keys(t).reduce((e,i)=>{let o=t[i];return o==null?e:e+`${i=i.includes("-")?i:i.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${o};`},"")}update(t,[e]){let{style:i}=t.element;if(this.ft===void 0)return this.ft=new Set(Object.keys(e)),this.render(e);for(let o of this.ft)e[o]==null&&(this.ft.delete(o),o.includes("-")?i.removeProperty(o):i[o]=null);for(let o in e){let r=e[o];if(r!=null){this.ft.add(o);let a=typeof r=="string"&&r.endsWith(ks);o.includes("-")||a?i.setProperty(o,a?r.slice(0,-11):r,a?Vi:""):i[o]=r}}return fe}});function _i(t){return Si({filename:`wind-${t.wind+1}.svg`,fromDirectionDeg:t.fromDirectionDeg,radius:t.radius,color:t.color})}function Zi(t){return Si({filename:`current-${t.current}.svg`,fromDirectionDeg:t.fromDirectionDeg,radius:t.radius,color:t.color})}function Si(t){let{filename:e,fromDirectionDeg:i,radius:o,color:r}=t,a=(i-180)*Math.PI/180,n=Ms[e];return l`<g style=${fr(r?{"--instrument-regular-secondary-color":r}:{})} transform="translate(${-Math.sin(a)*o} ${Math.cos(a)*o}) rotate(${180+i}) translate(-24, 0) scale(2)">
    ${n}
  </g>`}var Ms={"current-0.svg":l`<path d="M11 2V22H13V2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 2V22H13V2Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-1.svg":l`<path d="M11 7.00002L11 24L13 24L13 7.00005L11 7.00002Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79309 5.20723L12.0002 0.00012207L17.2073 5.20723L15.7931 6.62144L12.0002 2.82855L8.2073 6.62144L6.79309 5.20723Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 7.00002L11 24L13 24L13 7.00005L11 7.00002Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79309 5.20723L12.0002 0.00012207L17.2073 5.20723L15.7931 6.62144L12.0002 2.82855L8.2073 6.62144L6.79309 5.20723Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-2.svg":l`<path d="M10.9742 12.0003L10.9742 24.0049L12.9999 24.005L12.9999 12.0004L10.9742 12.0003Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79285 5.20747L12 0.000366211L17.2071 5.20747L15.7928 6.62169L12 2.82879L8.20706 6.62169L6.79285 5.20747Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99988 10.5861L12.207 5.37903L17.4141 10.5861L15.9999 12.0003L12.207 8.20745L8.41409 12.0003L6.99988 10.5861Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M10.9742 12.0003L10.9742 24.0049L12.9999 24.005L12.9999 12.0004L10.9742 12.0003Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79285 5.20747L12 0.000366211L17.2071 5.20747L15.7928 6.62169L12 2.82879L8.20706 6.62169L6.79285 5.20747Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99988 10.5861L12.207 5.37903L17.4141 10.5861L15.9999 12.0003L12.207 8.20745L8.41409 12.0003L6.99988 10.5861Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-3.svg":l`<path d="M11 18L11 24L13 24L13 18L11 18Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 18L11 24L13 24L13 18L11 18Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-4.svg":l`<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 22.5858L12.2071 17.3787L17.4142 22.5858L16 24L12.2071 20.2071L8.41421 24L7 22.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 22.5858L12.2071 17.3787L17.4142 22.5858L16 24L12.2071 20.2071L8.41421 24L7 22.5858Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-1.svg":l`<path d="M12 2C6.47715 2 2 6.47715 2 12H3.90476C3.90476 7.52912 7.52912 3.90476 12 3.90476V2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M22 12C22 6.47715 17.5228 2 12 2V3.90476C16.4709 3.90476 20.0952 7.52912 20.0952 12H22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M12 22C17.5228 22 22 17.5228 22 12H20.0952C20.0952 16.4709 16.4709 20.0952 12 20.0952V22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M2 12C2 17.5228 6.47715 22 12 22V20.0952C7.52912 20.0952 3.90476 16.4709 3.90476 12H2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M12 2C6.47715 2 2 6.47715 2 12H3.90476C3.90476 7.52912 7.52912 3.90476 12 3.90476V2Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M22 12C22 6.47715 17.5228 2 12 2V3.90476C16.4709 3.90476 20.0952 7.52912 20.0952 12H22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M12 22C17.5228 22 22 17.5228 22 12H20.0952C20.0952 16.4709 16.4709 20.0952 12 20.0952V22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M2 12C2 17.5228 6.47715 22 12 22V20.0952C7.52912 20.0952 3.90476 16.4709 3.90476 12H2Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-2.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-3.svg":l`<path d="M11 24L13 24L13 7L15 7L12 -1.74846e-07L9 7L11 7L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 21L8 19L11 19L11 21L8 21Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24L13 24L13 7L15 7L12 -1.74846e-07L9 7L11 7L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 21L8 19L11 19L11 21L8 21Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-4.svg":l`<path d="M11 24L13 24L13 7L15 7L12 -2.62268e-07L9 7L11 7L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M6 24L6 22L11 22L11 24L6 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24L13 24L13 7L15 7L12 -2.62268e-07L9 7L11 7L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M6 24L6 22L11 22L11 24L6 24Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-5.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 21L8 19H12V21H8Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 21L8 19H12V21H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-6.svg":l`<path d="M11 24H13L13 7L15 7L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7L15 7L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-7.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 18L8 16H12V18H8Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 18L8 16H12V18H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-8.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-9.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 15L8 13H12V15H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 15L8 13H12V15H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-10.svg":l`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 15L5 13H12V15H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 12L8 10H12V12H8Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 15L5 13H12V15H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 12L8 10H12V12H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-11.svg":l`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 20L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 20L5 22Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-12.svg":l`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-13.svg":l`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 15L5 13H12V15H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 15L5 13H12V15H5Z" fill="var(--instrument-regular-secondary-color)"/>`};function Pi(t){let{areas:e,outerRadius:i,innerRadius:o,extension:r,targetSize:a,margin:n=.06}=t;if(e.length===0){let P=a;return{radiusOffset:0,x:-P/2,y:-P/2,width:P,height:P,viewBox:`${-P/2} ${-P/2} ${P} ${P}`}}let v=a*(1-2*n),u=P=>{let I=Ai(e,i+P,o+P,r);return Math.max(I.xMax-I.xMin,I.yMax-I.yMin)},m=0,b=a;for(let P=0;P<16&&u(b)<v;P++)b*=2;for(let P=0;P<50;P++){let I=(m+b)/2;u(I)<v?m=I:b=I}let g=Math.max(0,m),C=Ai(e,i+g,o+g,r),y=C.xMax-C.xMin,H=C.yMax-C.yMin,k=Math.max(y,H)*(1+n*2),w=(C.xMin+C.xMax)/2,$=(C.yMin+C.yMax)/2,B=gr(w-k/2),Q=gr($-k/2),F=gr(k),U=gr(k);return{radiusOffset:g,x:B,y:Q,width:F,height:U,viewBox:`${B} ${Q} ${F} ${U}`}}function Ai(t,e,i,o){let r=e+o,a=i,n=1/0,v=-1/0,u=1/0,m=-1/0,b=(g,C)=>{g<n&&(n=g),g>v&&(v=g),C<u&&(u=C),C>m&&(m=C)};for(let g of t){let C=g.startAngle*Math.PI/180,y=g.endAngle*Math.PI/180;for(let w of[r,a])b(w*Math.sin(C),-w*Math.cos(C)),b(w*Math.sin(y),-w*Math.cos(y));let H=(g.startAngle%360+360)%360,E=(g.endAngle%360+360)%360,k=[0,90,180,270];for(let w of k)if(xs(H,E,w)){let $=w*Math.PI/180;for(let B of[r,a])b(B*Math.sin($),-B*Math.cos($))}}return n===1/0?{xMin:0,xMax:0,yMin:0,yMax:0}:{xMin:n,xMax:v,yMin:u,yMax:m}}function xs(t,e,i){let o=(t%360+360)%360,r=(e%360+360)%360,a=(i%360+360)%360;return o<=r?a>=o&&a<=r:a>=o||a<=r}function gr(t){return Math.round(t*1e4)/1e4}var Hs=Object.defineProperty,$s=Object.getOwnPropertyDescriptor,M=(t,e,i,o)=>{for(var r=o>1?void 0:o?$s(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Hs(e,i,r),r},$t=(t=>(t.single="single",t.double="double",t.doubleThin="doubleThin",t.triple="triple",t))($t||{}),ke=368/2,Ht=320/2,br=224/2,Bi=272/2,Ti=176/2;function Vs(t){switch(t){case"single":return Ht;case"double":return br;case"doubleThin":return Bi;case"triple":return Ti;default:throw new Error(`Unknown WatchCircleType: ${t}`)}}var Oi=4,L=class extends d{constructor(){super(...arguments),this._setpointId=`watch-setpoint-${Math.random().toString(36).slice(2,9)}`,this._newSetpointId=`watch-new-setpoint-${Math.random().toString(36).slice(2,9)}`,this.state=be.active,this.priority=D.regular,this.watchCircleType="single",this.northArrow=!1,this.atAngleSetpoint=!1,this.angleSetpointAtZeroDeadband=.5,this.setpointOverride=!1,this.touching=!1,this.animateSetpoint=!1,this._setpointCssAngle=0,this._setpointCssAngleInit=!1,this.areas=[],this.barAreas=[],this.needles=[],this.tickmarks=[],this.tickmarksInside=!1,this.tickmarkStyle=Y.regular,this.advices=[],this.crosshairEnabled=!1,this.showLabels=!1,this.vessels=[],this.wind=null,this.windFromDirectionDeg=null,this.windSymbolRadius=null,this.current=null,this.currentFromDirectionDeg=null,this.currentSymbolRadius=null,this.starboardPortIndicator=!1,this.clipTop=0,this.clipBottom=0,this.scaleWindIcon=1,this.zoomToFitArc=!1,this.tickFadeAngle=0,this.rotPosition=kt.innerCircle,this.rotStartAngle=0,this.rotEndAngle=0,this.rotPortStarboard=!1,this.rotAtZeroDeadband=Mt,this._rotationsPerMinute=0,this._resizeController=new nt(this,{}),this._rOff=0}set rotationsPerMinute(t){this._rotationsPerMinute=t,this._rotController&&(this._rotController.rotationsPerMinute=t)}get rotationsPerMinute(){return this._rotationsPerMinute}willUpdate(t){if(super.willUpdate(t),t.has("newAngleSetpoint")&&this.animateSetpoint){let e=t.get("newAngleSetpoint");if(e!==void 0&&this.newAngleSetpoint===void 0){this._departingNewAngleSetpoint=e,clearTimeout(this._animationTimer);let i=V1(this);this._animationTimer=setTimeout(()=>{this._departingNewAngleSetpoint=void 0},i)}}}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this._animationTimer),this._rotController=vr(this,this._rotController)}updated(t){super.updated(t);let e=this.rotType?this.renderRoot.querySelector("#rot-spinner"):null;if(!e){this._rotController=vr(this,this._rotController);return}(!this._rotController||this._rotController.el!==e)&&(this._rotController=vr(this,this._rotController),this._rotController=new ur(this,e,this._rotationsPerMinute))}get innerRingRadius(){return Vs(this.watchCircleType)}watchCircle(){let t=[];if(this.state!==be.off){if(t.push(l`
        <circle
          cx="0"
          cy="0"
          r="${172+this._rOff}"
          stroke="var(--instrument-frame-primary-color)"
          fill="none"
          stroke-width="24"
        />`),this.watchCircleType!=="single"){let o=Ht+this._rOff,r=(this.watchCircleType==="doubleThin"?Bi:br)+this._rOff,a=(o+r)/2,n=o-r;t.push(l`
            <circle cx="0" cy="0" r=${a} stroke="var(--instrument-frame-secondary-color)" stroke-width=${n} fill="none" />
            <circle cx="0" cy="0" r=${o} stroke="var(--instrument-frame-secondary-color)" stroke-width="1" fill="none" vector-effect="non-scaling-stroke" />
            <circle cx="0" cy="0" r=${r} stroke="var(--instrument-frame-secondary-color)" stroke-width="1" fill="none" vector-effect="non-scaling-stroke" />
        `)}if(this.watchCircleType==="triple"){let o=br+this._rOff,r=Ti+this._rOff,a=(o+r)/2,n=o-r;t.push(l`<circle cx="0" cy="0" r=${a} stroke="var(--instrument-frame-primary-color)" stroke-width=${n} fill="none" />`)}}let e=Math.max(200,ke+this._rOff+50),i=t;if(this.areas.length>0){let o=this.areas.map(n=>wt({startAngle:n.startAngle,endAngle:n.endAngle,R:ke+this._rOff,r:this.innerRingRadius+this._rOff,roundOutsideCut:n.roundOutsideCut,roundInsideCut:n.roundInsideCut})),r=l`<mask id="cutMask">
        <rect x="${-e}" y="${-e}" width="${e*2}" height="${e*2}" fill="black" />
        ${o.map(n=>l`<path d=${n} fill="white" vector-effect="non-scaling-stroke" stroke="white" stroke-width="1"/>`)}
      </mask>`,a=l`<clipPath id="rot-arc-clip">${this.areas.map(n=>l`<path d=${wt({startAngle:n.startAngle,endAngle:n.endAngle,R:ke+this._rOff+20,r:0,roundOutsideCut:n.roundOutsideCut,roundInsideCut:n.roundInsideCut})} />`)}</clipPath>`;i=[r,a,l`<g mask="url(#cutMask)">${t}</g>`],o.forEach(n=>{i.push(l`<path d=${n} fill="none" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>`)})}else this.state!==be.off?(i.push(sr("outerRing",{radius:ke+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"})),i.push(l`
          ${sr("innerRing",{radius:this.innerRingRadius+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"})}
        `)):i.push(l`
          ${sr("innerRing",{radius:ke+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"})}
        `);return i}_renderTickFadeDefs(){if(this.tickFadeAngle<=0||this.areas.length===0)return f;let t=this.areas[0],e=t.endAngle-t.startAngle,i=Math.min(this.tickFadeAngle,e/4);if(i<.5)return f;let{startAngle:o,endAngle:r}=t,a=ke+this._rOff+200,n=y=>y*Math.PI/180,v=y=>a*Math.sin(n(y)),u=y=>-a*Math.cos(n(y)),m=(y,H)=>{let E=v(y),k=u(y),w=v(H),$=u(H),B=H-y>180?1:0;return`M 0 0 L ${E} ${k} A ${a} ${a} 0 ${B} 1 ${w} ${$} Z`},b=(ke+this.innerRingRadius)/2+this._rOff,g=y=>b*Math.sin(n(y)),C=y=>-b*Math.cos(n(y));return l`
      <defs>
        <linearGradient id="tickFadeL" gradientUnits="userSpaceOnUse"
          x1="${g(o)}" y1="${C(o)}"
          x2="${g(o+i)}" y2="${C(o+i)}">
          <stop offset="0" stop-color="black" />
          <stop offset="1" stop-color="white" />
        </linearGradient>
        <linearGradient id="tickFadeR" gradientUnits="userSpaceOnUse"
          x1="${g(r-i)}" y1="${C(r-i)}"
          x2="${g(r)}" y2="${C(r)}">
          <stop offset="0" stop-color="white" />
          <stop offset="1" stop-color="black" />
        </linearGradient>
        <mask id="tickFadeMask" maskUnits="userSpaceOnUse"
          x="${-a}" y="${-a}" width="${a*2}" height="${a*2}">
          <path d="${m(o+i,r-i)}" fill="white" />
          <path d="${m(o,o+i)}" fill="url(#tickFadeL)" />
          <path d="${m(r-i,r)}" fill="url(#tickFadeR)" />
        </mask>
      </defs>
    `}renderCrosshair(t,e){let i=e&&e.positions.length>0,o=i?Math.max(...e.positions.map(a=>Math.abs(a.x!==0?a.x:a.y))):0,r=i?3/e.scale:0;return l`
      ${i?l`
        <defs>
          <mask
            id="crosshair-label-mask"
            maskUnits="userSpaceOnUse"
            x="-${t}" y="-${t}"
            width="${t*2}" height="${t*2}"
          >
            <rect x="-${t}" y="-${t}" width="${t*2}" height="${t*2}" fill="white"/>
            <!-- Annular ring knockout: hide crosshair between labels and inner ring -->
            <circle cx="0" cy="0" r="${e.innerRingRadius}" fill="black"/>
            <circle cx="0" cy="0" r="${o-r}" fill="white"/>
            <!-- Per-label rectangular knockouts -->
            ${e.positions.map(a=>{let n=12/e.scale,v=3/e.scale,u=n+v*2;return l`
                <rect
                  x="${a.x-u/2}" y="${a.y-u/2}"
                  width="${u}" height="${u}"
                  fill="black"
                  transform="rotate(${-(e.rotation??0)})"
                  transform-origin="${a.x} ${a.y}"
                />
              `})}
          </mask>
        </defs>`:f}
      <g mask=${i?"url(#crosshair-label-mask)":f}>
        <line
          x1="-${t}"
          y1="0"
          x2="${t}"
          y2="0"
          stroke="var(--instrument-frame-tertiary-color)"
          stroke-width="1"
          vector-effect="non-scaling-stroke"
        />
        <line
          x1="0"
          y1="-${t}"
          x2="0"
          y2="${t}"
          stroke="var(--instrument-frame-tertiary-color)"
          stroke-width="1"
          vector-effect="non-scaling-stroke"
        />
      </g>
    `}renderBars(){return this.barAreas.length===0?f:this.barAreas.map((t,e)=>{let i=Math.min(t.startAngle,t.endAngle),o=Math.max(t.startAngle,t.endAngle),r=wt({r:br+this._rOff,R:Ht+this._rOff,startAngle:i,endAngle:o,roundInsideCut:!1,roundOutsideCut:!1}),a=Ht+this._rOff+40,n=l`<mask id="barMask-${e}">
        <rect x="${-a}" y="${-a}" width="${a*2}" height="${a*2}" fill="black" />
        <path d=${wt({r:1,R:a,startAngle:i,endAngle:o,roundInsideCut:!1,roundOutsideCut:!1})} fill="white" />
      </mask>`;return l`
        ${n}
        <g mask="url(#cutMask)">
        <path 
          d=${r} 
          fill=${t.fillColor} 
          stroke=${t.fillColor} 
          stroke-width="1" 
          vector-effect="non-scaling-stroke" 
          mask="url(#barMask-${e})" 
          />
          </g>
          `})}renderNeedles(){return this.needles.length===0?f:this.needles.map(t=>l`
        <rect 
          transform="rotate(${t.angle})" 
          x="-4" y="${-(Ht+this._rOff)}" width="8" height="48" rx="4" 
          fill=${t.fillColor} 
          stroke=${t.strokeColor}
          stroke-width="1"
          vector-effect="non-scaling-stroke"
          paint-order="stroke fill"
        />
      `)}getScale({width:t,height:e}){let i=this.clientWidth,o=this.clientHeight;if(i===0||o===0){let a=this.parentElement?.getBoundingClientRect();a&&(i=a.width,o=a.height)}let r=Math.min(i/t,o/e);if(r===1/0||r<0)throw new Error("Watch scale is not valid");return r}getPadding(){return this.padding!==void 0?this.padding:this.tickmarks.length>0&&this.tickmarks.some(e=>e.text!==void 0)&&!this.tickmarksInside?24*2.5:24}render(){let t,e,i;if(this.arcFrame)this._rOff=this.arcFrame.radiusOffset,t=this.arcFrame.width,e=this.arcFrame.height,i=this.arcFrame.viewBox;else if(this.zoomToFitArc&&this.areas.length>0){let w=this.getPadding(),$=(176+w)*2,B=Pi({areas:this.areas,outerRadius:ke,innerRadius:this.innerRingRadius,extension:w,targetSize:$});this._rOff=B.radiusOffset,t=B.width,e=B.height,i=B.viewBox}else{this._rOff=0,t=(176+this.getPadding())*2,e=t*(1-this.clipTop/100-this.clipBottom/100);let w=-t/2+t*this.clipTop/100;i=`-${t/2} ${w} ${t} ${e}`}let o=this._rOff,r=this.getScale({width:t,height:e}),a=this.renderSetpoint(),n=(this.tickmarksInside?this.innerRingRadius:ke)+o,v=Math.max(...this.tickmarks.map(w=>w.text?.length??0)),u=this.tickmarks.map(w=>Ye(w.angle,{size:w.type,style:this.tickmarkStyle,scale:r,text:this.showLabels?void 0:w.text,inside:this.tickmarksInside,textRadius:n,rotation:this.rotation,maxDigits:v,color:w.color,radiusOffset:o})),m=this.advices?this.advices.map(w=>T1(w,o)):f,b=this.tickmarksInside&&this.showLabels,g=!this.northArrow,C=this.showLabels?ko({scale:r,inside:this.tickmarksInside,innerRadius:this.innerRingRadius+o,includeNorth:g}):void 0,y=C?N1({scale:r,rotation:this.rotation,inside:this.tickmarksInside,innerRadius:this.innerRingRadius+o,includeNorth:g}):f,H=this.northArrow?F1({scale:r,rotation:this.rotation,inside:this.northArrowInside??this.tickmarksInside}):f,E=this.wind!=null&&this.windFromDirectionDeg!=null?l`<g transform="scale(${this.scaleWindIcon})">${_i({wind:this.wind,fromDirectionDeg:this.windFromDirectionDeg,radius:this.windSymbolRadius??192,color:this.windColor})}</g>`:f,k=this.current!=null&&this.currentFromDirectionDeg!=null?Zi({current:this.current,fromDirectionDeg:this.currentFromDirectionDeg,radius:this.currentSymbolRadius??192,color:this.currentColor}):f;return c`
      <svg
        width="100%"
        height="100%"
        viewBox=${i}
        style="--scale: ${r}"
        transform="rotate(${this.rotation??0})"
      >
        ${this.watchCircle()} ${this.renderBars()}
        ${this.crosshairEnabled?this.renderCrosshair(ke+o,b&&C?{positions:C,rotation:this.rotation,scale:r,innerRingRadius:this.innerRingRadius+o}:void 0):f}
        ${H} ${this.renderStarboardPortIndicator()} ${k}
        ${this._renderTickFadeDefs()} ${E}
        ${this.tickFadeAngle>0&&this.areas.length>0?l`<g mask="url(#tickFadeMask)">${u}</g>`:u}
        ${this.areas.length>0?l`<g clip-path="url(#rot-arc-clip)">${this.renderRot()}</g>`:this.renderRot()}
        ${m} ${a}
        ${this.tickFadeAngle>0&&this.areas.length>0?l`<g mask="url(#tickFadeMask)">${y}</g>`:y}
        ${this.renderVesselImage()} ${this.renderNeedles()}
      </svg>
    `}getRotColors(){let e=(this.rotPriority??this.priority)===D.enhanced;if(this.rotPortStarboard){let i;if(this.rotType===lt.bar){let o=((this.rotEndAngle-this.rotStartAngle)%360+360)%360;i=o<=180?o:o-360}else i=this._rotationsPerMinute;if(i>0)return{dotColor:"var(--instrument-starboard-secondary-color)",barBgColor:"var(--instrument-starboard-primary-color)"};if(i<0)return{dotColor:"var(--instrument-port-secondary-color)",barBgColor:"var(--instrument-port-primary-color)"}}return{dotColor:e?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)",barBgColor:e?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}}renderRot(){if(!this.rotType)return f;let{dotColor:t,barBgColor:e}=this.getRotColors(),i=this._rOff;if(this.rotType===lt.bar){let n=wo(this.rotStartAngle,this.rotEndAngle),v=Lo(this.rotPosition,i),u=Number.isFinite(this.rotAtZeroDeadband)?this.rotAtZeroDeadband:Mt;return n<Math.max(u,v)?I1(e,this.rotStartAngle,this.rotPosition,i):l`
        ${R1({startAngle:this.rotStartAngle,endAngle:this.rotEndAngle,barColor:e,position:this.rotPosition,maskId:"rot-bar-mask",radiusOffset:i})}
        ${l`<g clip-path="url(#rot-bar-mask)">
            <g id="rot-spinner">
              ${j1(t,this.rotPosition,i)}
            </g>
          </g>`}
      `}let a=(this.rotPriority??this.priority)===D.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";return this.rotPortStarboard&&(this._rotationsPerMinute>0?a="var(--instrument-starboard-secondary-color)":this._rotationsPerMinute<0&&(a="var(--instrument-port-secondary-color)")),l`
      <g id="rot-spinner">
        ${D1(a,this.rotPosition,i)}
      </g>
    `}renderSetpoint(){if(this.angleSetpoint===void 0)return f;let t=Z1({state:this.state,priority:this.priority,atSetpoint:this.atAngleSetpoint,angleSetpoint:this.angleSetpoint,setpointAtZeroDeadband:this.angleSetpointAtZeroDeadband,newAngleSetpoint:this.newAngleSetpoint,touching:this.touching,setpointOverride:this.setpointOverride}),{visualState:e,colorMode:i,disabled:o,hasNewSetpoint:r}=t,a=mo(e),n=go+this._rOff+a-Oi,v=r?.75:1,u=fo({visualState:e,colorMode:i,disabled:o,id:this._setpointId}),m=this.animateSetpoint,b=this._departingNewAngleSetpoint!==void 0,g=this.angleSetpoint+90;this._setpointCssAngleInit?this._setpointCssAngle=_1(this._setpointCssAngle,g):(this._setpointCssAngle=g,this._setpointCssAngleInit=!0);let C=m?l`
        <g style="transform: rotate(${this._setpointCssAngle}deg) translateX(${-n}px) rotate(270deg); opacity: ${v}; transition: transform var(${yt}, ${dr}) ease-out, opacity var(${yt}, ${dr}) ease-out;">
          ${u}
        </g>
      `:l`
        <g transform="rotate(${this.angleSetpoint+90}) translate(${-n}, 0) rotate(270)" opacity="${v}">
          ${u}
        </g>
      `;if(r||b){let y=r,H=y?this.newAngleSetpoint:this._departingNewAngleSetpoint,E=y?1:0,k=mo(cr.focus),w=go+this._rOff+k-Oi,$=fo({visualState:cr.focus,colorMode:i,disabled:!1,id:this._newSetpointId});if(m){let B=`var(${yt}, ${dr})`;return l`
          ${C}
          <g style="transform: rotate(${H+90}deg) translateX(${-w}px) rotate(270deg); opacity: ${E}; transition: opacity ${B} ease-out;">
            ${$}
          </g>
        `}return l`
        ${C}
        <g transform="rotate(${H+90}) translate(${-w}, 0) rotate(270)" opacity="${E}">
          ${$}
        </g>
      `}return C}renderVesselImage(){return this.vessels.length===0?f:this.vessels.map(t=>{let e;switch(t.size){case Pe.large:e=224;break;case Pe.medium:e=160;break;default:e=100}let i=e/160;return l`<g style="transform: ${t.transform} scale(${i}) translate(-80px, -80px) ">${mr[t.vesselImage]}</g>`})}renderStarboardPortIndicator(){return this.starboardPortIndicator?[st(0,180,"var(--instrument-starboard-secondary-color)","var(--instrument-starboard-secondary-color)"),st(180,360,"var(--instrument-port-secondary-color)","var(--instrument-port-secondary-color)")]:f}};L.styles=x(A1);M([s({type:String})],L.prototype,"state",2);M([s({type:String})],L.prototype,"priority",2);M([s({type:String})],L.prototype,"watchCircleType",2);M([s({type:Boolean})],L.prototype,"northArrow",2);M([s({type:Boolean})],L.prototype,"northArrowInside",2);M([s({type:Number})],L.prototype,"angleSetpoint",2);M([s({type:Number})],L.prototype,"newAngleSetpoint",2);M([s({type:Boolean})],L.prototype,"atAngleSetpoint",2);M([s({type:Number})],L.prototype,"angleSetpointAtZeroDeadband",2);M([s({type:Boolean})],L.prototype,"setpointOverride",2);M([s({type:Boolean})],L.prototype,"touching",2);M([s({type:Boolean})],L.prototype,"animateSetpoint",2);M([re()],L.prototype,"_departingNewAngleSetpoint",2);M([s({type:Number})],L.prototype,"padding",2);M([s({type:Array,attribute:!1})],L.prototype,"areas",2);M([s({type:Array,attribute:!1})],L.prototype,"barAreas",2);M([s({type:Array,attribute:!1})],L.prototype,"needles",2);M([s({type:Array,attribute:!1})],L.prototype,"tickmarks",2);M([s({type:Boolean})],L.prototype,"tickmarksInside",2);M([s({type:String})],L.prototype,"tickmarkStyle",2);M([s({type:Array,attribute:!1})],L.prototype,"advices",2);M([s({type:Boolean})],L.prototype,"crosshairEnabled",2);M([s({type:Boolean})],L.prototype,"showLabels",2);M([s({type:Array,attribute:!1})],L.prototype,"vessels",2);M([s({type:Number})],L.prototype,"wind",2);M([s({type:Number})],L.prototype,"windFromDirectionDeg",2);M([s({type:Number})],L.prototype,"windSymbolRadius",2);M([s({type:String})],L.prototype,"windColor",2);M([s({type:Number})],L.prototype,"current",2);M([s({type:Number})],L.prototype,"currentFromDirectionDeg",2);M([s({type:Number})],L.prototype,"currentSymbolRadius",2);M([s({type:String})],L.prototype,"currentColor",2);M([s({type:Boolean})],L.prototype,"starboardPortIndicator",2);M([s({type:Number})],L.prototype,"clipTop",2);M([s({type:Number})],L.prototype,"clipBottom",2);M([s({type:Number})],L.prototype,"scaleWindIcon",2);M([s({type:Number})],L.prototype,"rotation",2);M([s({type:Boolean})],L.prototype,"zoomToFitArc",2);M([s({attribute:!1})],L.prototype,"arcFrame",2);M([s({type:Number})],L.prototype,"tickFadeAngle",2);M([s({type:String})],L.prototype,"rotType",2);M([s({type:String})],L.prototype,"rotPosition",2);M([s({type:Number})],L.prototype,"rotStartAngle",2);M([s({type:Number})],L.prototype,"rotEndAngle",2);M([s({type:String})],L.prototype,"rotPriority",2);M([s({type:Boolean})],L.prototype,"rotPortStarboard",2);M([s({type:Number})],L.prototype,"rotAtZeroDeadband",2);M([s({type:Number})],L.prototype,"rotationsPerMinute",1);L=M([h("obc-watch")],L);var Cr=(t=>(t.HDG="HDG",t.COG="COG",t))(Cr||{});function Mo(t,e,i=D.regular,o=0){let r=i===D.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";return t==="HDG"?l`
      <g transform="rotate(${e}) translate(-256, ${-256-o})">

<path d="M254.654 100.32C255.219 99.1903 256.906 99.2277 257.396 100.433L272.312 137.092L272.388 137.301C273.067 139.455 270.647 141.314 268.676 140.13V140.129L256 132.582L243.323 140.129L243.324 140.13C241.289 141.352 238.777 139.332 239.688 137.092L254.604 100.433L254.654 100.32Z"
 fill=${r} stroke="var(--border-silhouette-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>
      </g>
    `:t==="COG"?l`
      <g transform="rotate(${e}) translate(-256, ${-256-o})">
<mask id="path-1-outside-1_133_32856" maskUnits="userSpaceOnUse" x="238" y="99" width="36" height="42" fill="black">
<rect fill="white" x="238" y="99" width="36" height="42"/>
<path fill-rule="evenodd" clip-rule="evenodd" vector-effect="non-scaling-stroke" d="M256 127.334L265.867 133.192L256 108.941L246.133 133.192L256 127.334ZM255.067 100.621C255.404 99.7929 256.596 99.7929 256.933 100.621L271.849 137.28C272.567 139.046 270.584 140.693 268.933 139.701L256 132L243.067 139.701C241.416 140.693 239.433 139.046 240.151 137.28L255.067 100.621Z"/>
</mask>
<path fill-rule="evenodd" clip-rule="evenodd" d="M256 127.334L265.867 133.192L256 108.941L246.133 133.192L256 127.334ZM255.067 100.621C255.404 99.7929 256.596 99.7929 256.933 100.621L271.849 137.28C272.567 139.046 270.584 140.693 268.933 139.701L256 132L243.067 139.701C241.416 140.693 239.433 139.046 240.151 137.28L255.067 100.621Z"
   fill=${r} />
<path d="M256 127.334L256.511 126.474L256 126.171L255.489 126.474L256 127.334ZM265.867 133.192L265.357 134.052L267.914 135.571L266.793 132.816L265.867 133.192ZM256 108.941L256.926 108.564L256 106.288L255.074 108.564L256 108.941ZM246.133 133.192L245.207 132.816L244.086 135.571L246.643 134.052L246.133 133.192ZM255.067 100.621L254.14 100.244L255.067 100.621ZM256.933 100.621L257.86 100.244L256.933 100.621ZM271.849 137.28L270.922 137.657L271.849 137.28ZM268.933 139.701L269.448 138.844L269.445 138.842L268.933 139.701ZM256 132L256.512 131.141L256 130.836L255.488 131.141L256 132ZM243.067 139.701L242.555 138.842L242.552 138.844L243.067 139.701ZM240.151 137.28L241.078 137.657L240.151 137.28ZM255.489 128.193L265.357 134.052L266.378 132.333L256.511 126.474L255.489 128.193ZM266.793 132.816L256.926 108.564L255.074 109.318L264.941 133.569L266.793 132.816ZM255.074 108.564L245.207 132.816L247.059 133.569L256.926 109.318L255.074 108.564ZM246.643 134.052L256.511 128.193L255.489 126.474L245.622 132.333L246.643 134.052ZM255.993 100.998C255.994 100.994 255.996 100.992 255.996 100.992C255.996 100.992 255.995 100.993 255.994 100.994C255.991 100.997 255.988 101 255.986 101.002C255.984 101.003 255.984 101.002 255.987 101.002C255.99 101.001 255.994 101 256 101C256.006 101 256.01 101.001 256.013 101.002C256.016 101.002 256.016 101.003 256.014 101.002C256.012 101 256.009 100.997 256.006 100.994C256.005 100.993 256.004 100.992 256.004 100.992C256.004 100.992 256.006 100.994 256.007 100.998L257.86 100.244C257.185 98.5852 254.815 98.5852 254.14 100.244L255.993 100.998ZM256.007 100.998L270.922 137.657L272.775 136.903L257.86 100.244L256.007 100.998ZM270.922 137.657C271.255 138.473 270.33 139.373 269.448 138.844L268.418 140.558C270.838 142.012 273.879 139.618 272.775 136.903L270.922 137.657ZM269.445 138.842L256.512 131.141L255.488 132.859L268.422 140.56L269.445 138.842ZM255.488 131.141L242.555 138.842L243.578 140.56L256.512 132.859L255.488 131.141ZM242.552 138.844C241.67 139.373 240.745 138.473 241.078 137.657L239.225 136.903C238.121 139.618 241.162 142.012 243.582 140.558L242.552 138.844ZM241.078 137.657L255.993 100.998L254.14 100.244L239.225 136.903L241.078 137.657Z" 
fill="var(--border-silhouette-color)" vector-effect="non-scaling-stroke" mask="url(#path-1-outside-1_133_32856)"/>

      </g>
    `:[]}var yr=class{constructor(e){this.atSetpoint=!1,this.touching=!1,this.autoAtSetpoint=!0,this.setpointOverride=!1,this.animateSetpoint=!1,this.autoAtSetpointDeadband=e?.defaultDeadband??2,this.setpointAtZeroDeadband=e?.defaultZeroDeadband??.5,this._angularWraparound=e?.angularWraparound??!1,this._onAnimationEnd=e?.onAnimationEnd}sync(e){let i=this.newSetpoint;(e.setpoint!==void 0||"setpoint"in e)&&(this.setpoint=e.setpoint),(e.newSetpoint!==void 0||"newSetpoint"in e)&&(this.newSetpoint=e.newSetpoint),e.atSetpoint!==void 0&&(this.atSetpoint=e.atSetpoint),e.touching!==void 0&&(this.touching=e.touching),e.autoAtSetpoint!==void 0&&(this.autoAtSetpoint=e.autoAtSetpoint),e.autoAtSetpointDeadband!==void 0&&(this.autoAtSetpointDeadband=e.autoAtSetpointDeadband),e.setpointAtZeroDeadband!==void 0&&(this.setpointAtZeroDeadband=e.setpointAtZeroDeadband),e.setpointOverride!==void 0&&(this.setpointOverride=e.setpointOverride),e.animateSetpoint!==void 0&&(this.animateSetpoint=e.animateSetpoint),i!==void 0&&this.newSetpoint===void 0&&this.animateSetpoint&&(this.departingNewSetpoint=i,clearTimeout(this._animationTimer),this._animationTimer=setTimeout(()=>{this.departingNewSetpoint=void 0,this._onAnimationEnd?.()},lr))}dispose(){clearTimeout(this._animationTimer)}computeAtSetpoint(e){return S1({value:e,setpoint:this.setpoint,touching:this.touching,auto:this.autoAtSetpoint,deadband:this.autoAtSetpointDeadband,atSetpointManual:this.atSetpoint,angularWraparound:this._angularWraparound})}};var _s=Object.defineProperty,Zs=Object.getOwnPropertyDescriptor,A=(t,e,i,o)=>{for(var r=o>1?void 0:o?Zs(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&_s(e,i,r),r};var Z=class extends d{constructor(){super(...arguments),this.heading=0,this.courseOverGround=0,this.headingSetpoint=null,this.atHeadingSetpoint=!1,this.headingSetpointAtZeroDeadband=.5,this.headingSetpointOverride=!1,this.autoAtHeadingSetpoint=!0,this.autoAtHeadingSetpointDeadband=2,this.animateSetpoint=!1,this.touching=!1,this.headingAdvices=[],this.windSpeed=null,this.windFromDirection=null,this.currentSpeed=null,this.currentFromDirection=null,this.vesselImage=Oe.genericTop,this.rotationsPerMinute=1,this.rotType=lt.dots,this.rotPosition=kt.innerCircle,this.rotMaxValue=10,this.rotArcExtent=60,this.rotPortStarboard=!1,this.rotAtZeroDeadband=Mt,this.direction="northUp",this.state=be.active,this.priority=D.regular,this.priorityElements=["hdg"],this.showLabels=!1,this.tickmarksInside=!1,this._headingSp=new yr({angularWraparound:!0,onAnimationEnd:()=>this.requestUpdate()}),this._resizeController=new nt(this,{})}willUpdate(t){super.willUpdate(t),this._headingSp.sync({setpoint:this.headingSetpoint??void 0,newSetpoint:this.newHeadingSetpoint,atSetpoint:this.atHeadingSetpoint,touching:this.touching,autoAtSetpoint:this.autoAtHeadingSetpoint,autoAtSetpointDeadband:this.autoAtHeadingSetpointDeadband,setpointAtZeroDeadband:this.headingSetpointAtZeroDeadband,setpointOverride:this.headingSetpointOverride,animateSetpoint:this.animateSetpoint})}disconnectedCallback(){super.disconnectedCallback(),this._headingSp.dispose()}getPadding(){let e=512-Math.min(this.clientHeight,this.clientWidth),i=e/128,o;return e>0?o=i*48:o=i*6,72+o}get angleAdviceRaw(){return this.headingAdvices.map(({minAngle:t,maxAngle:e,hinted:i,type:o})=>{let r=this.heading>=t&&this.heading<=e?j.triggered:i?j.hinted:j.regular;return{minAngle:t,maxAngle:e,type:o,state:r}})}priorityFor(t){return(Array.isArray(this.priorityElements)?this.priorityElements:[]).includes(t)?this.priority:D.regular}colorFor(t){return this.priorityFor(t)===D.enhanced?"var(--instrument-enhanced-secondary-color)":void 0}getRotation(){if(this.direction!=="northUp"){if(this.direction==="headingUp")return-this.heading;if(this.direction==="courseUp")return-this.courseOverGround}}render(){let t=[{angle:0,type:ee.main},{angle:90,type:ee.main},{angle:180,type:ee.main},{angle:270,type:ee.main}],e=this.getPadding(),i=(176+e)*2,o=`-${i/2} -${i/2} ${i} ${i}`;return c`
      <div class="container">
        <obc-watch
          .touching=${this.touching}
          .padding=${e}
          .advices=${this.angleAdviceRaw}
          .tickmarks=${t}
          .state=${this.state}
          .watchCircleType=${$t.triple}
          .showLabels=${this.showLabels}
          .tickmarksInside=${this.tickmarksInside}
          .crosshairEnabled=${!0}
          .northArrow=${!0}
          .angleSetpoint=${this.headingSetpoint??void 0}
          .newAngleSetpoint=${this.newHeadingSetpoint}
          .atAngleSetpoint=${this._headingSp.computeAtSetpoint(this.heading)}
          .angleSetpointAtZeroDeadband=${this.headingSetpointAtZeroDeadband}
          .setpointOverride=${this.headingSetpointOverride}
          .priority=${this.priority}
          .animateSetpoint=${this.animateSetpoint}
          .vessels=${[{size:Pe.medium,vesselImage:this.vesselImage,transform:`rotate(${this.heading}deg)`}]}
          .wind=${this.windSpeed}
          .windFromDirectionDeg=${this.windFromDirection}
          .windColor=${this.colorFor("wind")}
          .current=${this.currentSpeed}
          .currentFromDirectionDeg=${this.currentFromDirection}
          .currentColor=${this.colorFor("current")}
          .rotation=${this.getRotation()}
          .rotType=${this.rotType}
          .rotPosition=${this.rotPosition}
          .rotStartAngle=${this.heading+(this.getRotation()??0)}
          .rotEndAngle=${this.heading+this.rotationsPerMinute/(this.rotMaxValue||1)*this.rotArcExtent+(this.getRotation()??0)}
          .rotPriority=${this.priorityFor("rot")}
          .rotPortStarboard=${this.rotPortStarboard}
          .rotAtZeroDeadband=${this.rotAtZeroDeadband}
          .rotationsPerMinute=${this.rotationsPerMinute}
        >
        </obc-watch>
        <svg viewBox="${o}">
          ${Mo(Cr.HDG,this.heading+(this.getRotation()??0),this.priorityFor("hdg"))}
          ${Mo(Cr.COG,this.courseOverGround+(this.getRotation()??0),this.priorityFor("cog"))}
        </svg>
      </div>
    `}};Z.styles=p`
    * {
      box-sizing: border-box;
    }

    .container {
      position: relative;
      width: 100%;
      height: 100%;
    }

    .container > * {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }

    :host {
      display: block;
      width: 100%;
      height: 100%;
    }
  `;A([s({type:Number})],Z.prototype,"heading",2);A([s({type:Number})],Z.prototype,"courseOverGround",2);A([s({type:Number})],Z.prototype,"headingSetpoint",2);A([s({type:Number})],Z.prototype,"newHeadingSetpoint",2);A([s({type:Boolean})],Z.prototype,"atHeadingSetpoint",2);A([s({type:Number})],Z.prototype,"headingSetpointAtZeroDeadband",2);A([s({type:Boolean})],Z.prototype,"headingSetpointOverride",2);A([s({type:Boolean,attribute:!1})],Z.prototype,"autoAtHeadingSetpoint",2);A([s({type:Number})],Z.prototype,"autoAtHeadingSetpointDeadband",2);A([s({type:Boolean})],Z.prototype,"animateSetpoint",2);A([s({type:Boolean})],Z.prototype,"touching",2);A([s({type:Array,attribute:!1})],Z.prototype,"headingAdvices",2);A([s({type:Number})],Z.prototype,"windSpeed",2);A([s({type:Number})],Z.prototype,"windFromDirection",2);A([s({type:Number})],Z.prototype,"currentSpeed",2);A([s({type:Number})],Z.prototype,"currentFromDirection",2);A([s({type:String})],Z.prototype,"vesselImage",2);A([s({type:Number})],Z.prototype,"rotationsPerMinute",2);A([s({type:String})],Z.prototype,"rotType",2);A([s({type:String})],Z.prototype,"rotPosition",2);A([s({type:Number})],Z.prototype,"rotMaxValue",2);A([s({type:Number})],Z.prototype,"rotArcExtent",2);A([s({type:Boolean})],Z.prototype,"rotPortStarboard",2);A([s({type:Number})],Z.prototype,"rotAtZeroDeadband",2);A([s({type:String})],Z.prototype,"direction",2);A([s({type:String})],Z.prototype,"state",2);A([s({type:String})],Z.prototype,"priority",2);A([s({type:Array,attribute:!1})],Z.prototype,"priorityElements",2);A([s({type:Boolean})],Z.prototype,"showLabels",2);A([s({type:Boolean})],Z.prototype,"tickmarksInside",2);Z=A([h("obc-compass")],Z);function xo({height:t,minValue:e,maxValue:i,min:o,max:r,fill:a,stroke:n,x1:v}){let b=v+8+4,g=8/2,C=pe(o,e,i,t)-2*g,y=pe(r,e,i,t)+2*g,H=`M ${v+4} ${C} 
                    A ${g} ${g} 0 0 0 ${b} ${C}
                    V ${y}
                    A ${g} ${g} 0 0 0 ${v+4} ${y}
                    Z`;return l`<path d=${H} fill=${a} stroke=${n} stroke-width="1" vector-effect="non-scaling-stroke" />`}function wr({height:t,scaleWidth:e,minValue:i,maxValue:o,value:r,style:a,x1:n}){if(r>=o||r<=i)return null;let v=bo(a),u=pe(r,i,o,t);return l`<line x1=${n-2} x2=${n+e} y1=${u}  y2=${u} stroke=${v} stroke-width="1" vector-effect="non-scaling-stroke"/>`}function Ei(t,e,i,o,r,a){let n=o/2-r,v=-o/2,u=o/2-r,m=[];if(a.min>e){let b=pe(a.min,e,i,t);m.push(l`<line x1=${v} x2=${u} y1=${b} y2=${b} 
                    stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke" 
                    stroke-dasharray="4 4"/>`)}if(a.max<i){let b=pe(a.max,e,i,t);m.push(l`<line x1=${v} x2=${u} y1=${b} y2=${b} 
                    stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke" 
                    stroke-dasharray="4 4"/>`)}if(a.type===ce.caution){let b,g="var(--instrument-frame-primary-color)";a.state===j.hinted?b="var(--instrument-frame-tertiary-color)":a.state===j.regular?b="var(--instrument-tick-mark-tertiary-color)":(b="var(--on-caution-active-color)",g="var(--alert-caution-color)");let C=[],y=50;for(let k=-128;k<224;k+=16)C.push(l`<g transform="translate(0 ${-k}) ">
            <path d="M 50 0 L 0 ${y}" stroke=${b} stroke-width="6"/>
            </g>
            `);let H=`adviceMask-${a.min}-${a.max}`,E=Y.regular;return a.state===j.regular?E=Y.regular:a.state===j.triggered&&(E=Y.enhanced),l`
            <mask id=${H}>
                ${xo({height:t,minValue:e,maxValue:i,min:a.min,max:a.max,fill:"white",stroke:"black",x1:n})}
            </mask>
            <g mask="url(#${H})">
                ${g?l`<rect x="-256" y="-512" width="512" height="1024" fill="${g}"/>`:f}
                ${C}
            </g>
            ${xo({height:t,minValue:e,maxValue:i,min:a.min,max:a.max,fill:"none",stroke:b,x1:n})}
            ${wr({height:t,scaleWidth:r,minValue:e,maxValue:i,value:a.min,style:E,x1:n})}
            ${wr({height:t,scaleWidth:r,minValue:e,maxValue:i,value:a.max,style:E,x1:n})}
            ${m}
        `}else{let b,g,C;return a.state===j.hinted?(b="var(--instrument-frame-tertiary-color)",C="var(--instrument-frame-primary-color)",g=Y.regular):a.state===j.regular?(b="var(--instrument-regular-secondary-color)",C="var(--instrument-frame-primary-color)",g=Y.regular):(b="var(--instrument-enhanced-secondary-color)",C=b,g=Y.regular),l`
            ${xo({height:t,minValue:e,maxValue:i,min:a.min,max:a.max,fill:C,stroke:b,x1:n})}
            ${wr({height:t,scaleWidth:r,minValue:e,maxValue:i,value:a.min,style:g,x1:n})}
            ${wr({height:t,scaleWidth:r,minValue:e,maxValue:i,value:a.max,style:g,x1:n})}
            ${m}
        `}}function Di({height:t,width:e,scaleWidth:i,minValue:o,maxValue:r},a,n,v,u,m,b){let C=`M -${e/2} 0  V -${t/2-8}  a 8 8 0 0 1 8 -8 h ${e-16} a 8 8 0 0 1 8 8 V ${t/2-8} a 8 8 0 0 1 -8 8 h -${e-16} a 8 8 0 0 1 -8 -8 Z`,y=l`
      <path d=${C} 
       fill=${v.container}
       />
  `,H=e-i-8,E=l`
      <path d="M -${e/2} 0  V -${t/2-8}  a 8 8 0 0 1 8 -8 h ${H} V ${t/2} h -${H} a 8 8 0 0 1 -8 -8 Z" 
       stroke="var(--instrument-frame-secondary-color)"
       fill="var(--instrument-frame-secondary-color)"
       vector-effect="non-scaling-stroke"
       />
  `,k=l`
      <path d=${C} 
      stroke="var(--instrument-frame-tertiary-color)" 
      fill="none" 
      vector-effect="non-scaling-stroke"/>
  `;u.off&&(E=f);let{boxFill:w,boxStroke:$,barFill:B,barStroke:Q}=Ss(u.priority===D.enhanced),F=[],U="boxMask",P=u.hideContainer?f:l`
  <defs>
  <mask id=${U}>
  <path d=${C} fill="white" stroke="white" vector-effect="non-scaling-stroke"/>
  </defs>`,I=u.hideContainer?void 0:`url(#${U})`,ne=[];if(m.mainTickmarks)for(let te of m.mainTickmarks){if(te<o||te>r)continue;let _e=pe(te,o,r,t);F.push(l`<line x1=${-e/2} x2=${e/2} y1=${_e} y2=${_e} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`),ne.push(te)}let Ve=e/2-i+4;if(m.primaryTickmarkInterval!==void 0&&m.primaryTickmarkInterval>0&&Number.isFinite(m.primaryTickmarkInterval)){let{svgs:te,values:_e}=zi({height:t,interval:m.primaryTickmarkInterval,minValue:o,maxValue:r,tickmarksX:Ve,tickmarksWidth:e/2-Ve,skipValues:ne});F.push(...te),ne.push(..._e)}if(m.secondaryTickmarkInterval!==void 0&&m.secondaryTickmarkInterval>0&&Number.isFinite(m.secondaryTickmarkInterval)){let{svgs:te,values:_e}=zi({height:t,interval:m.secondaryTickmarkInterval,minValue:o,maxValue:r,tickmarksX:Ve,tickmarksWidth:8,skipValues:ne});F.push(...te),ne.push(..._e)}let rt=-e/2,Vo=e-i,Za=a.map(te=>{let _e=pe(te.min,o,r,t),Zo=pe(te.max,o,r,t),Pa=Math.min(_e,Zo),Oa=Math.abs(Zo-_e);return l`<rect width=${Vo} height=${Oa} x=${rt} y=${Pa} fill=${te.fill??w} stroke=${te.fill??$} vector-effect="non-scaling-stroke"/>`}),Sa=b.map(te=>Ei(t,o,r,e,i,te)),Aa=n?l`
<rect x=${rt} y=${pe(n.value,o,r,t)-4} width=${Vo} height="8" rx="4" fill=${B} stroke=${Q} vector-effect="non-scaling-stroke"/>
`:f,_o=[P,k,l`<g mask=${I}>${F}${Za} </g>`,Sa,Aa];return u.hideContainer||_o.splice(0,0,[y,E]),_o}function pe(t,e,i,o){let r=i-e;return(-t+e)*o/r+o/2}function zi({height:t,interval:e,tickmarksX:i,tickmarksWidth:o,minValue:r,maxValue:a,skipValues:n}){let v=[],u=[];for(let m=0;m<a;m+=e){if(n.includes(m))continue;let b=pe(m,r,a,t);u.push(m),v.push(l`<line x1=${i} x2=${i+o} y1=${b} y2=${b} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`)}for(let m=-e;m>r;m-=e){if(n.includes(m))continue;let b=pe(m,r,a,t);u.push(m),v.push(l`<line x1=${i} x2=${i+o} y1=${b} y2=${b} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`)}return{svgs:v,values:u}}function Ss(t){return t?{boxFill:"var(--instrument-enhanced-tertiary-color)",boxStroke:"var(--instrument-enhanced-tertiary-color)",barFill:"var(--instrument-enhanced-secondary-color)",barStroke:"var(--instrument-enhanced-tertiary-color)"}:{boxFill:"var(--instrument-regular-tertiary-color)",boxStroke:"var(--instrument-regular-tertiary-color)",barFill:"var(--instrument-regular-secondary-color)",barStroke:"var(--instrument-regular-tertiary-color)"}}var As=Object.defineProperty,Ps=Object.getOwnPropertyDescriptor,Me=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ps(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&As(e,i,r),r},he=class extends d{constructor(){super(...arguments),this.depth=0,this.draft=0,this.advice=[],this.vesselScale=1,this.instrumentRange=10,this.primaryTickmarkInterval=50,this.secondaryTickmarkInterval=10,this.vesselImage=Oe.psvFore,this.priority=D.regular,this._boxWidth=336,this._gaugeWidth=72,this._scaleWidth=24}_toValue(t){return-t}_toTranslatedValue(t){return t*(this._boxWidth/2)/this.instrumentRange}_getAdvice(){return this.advice.map(t=>{let i=this.depth>=t.min&&this.depth<=t.max?j.triggered:t.hinted?j.hinted:j.regular;return{...t,min:this._toValue(t.max),max:this._toValue(t.min),state:i}})}render(){let t=this._boxWidth/2-this._gaugeWidth/2,e=8,i=l`
    <rect fill="url(#seabedPattern)" y=${this._toTranslatedValue(this.depth)} x=${-this._boxWidth/2} width=${this._boxWidth-this._gaugeWidth} height=${this._toTranslatedValue(this.instrumentRange-this.depth)} fill="red" />
    `,o=this.priority===D.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)",r=this.vesselScale*50/this.instrumentRange;return c`
      <div class="container">
        <svg viewbox="-200 -200 400 400">
          <rect
            mask="url(#heaveClip)"
            x=${-this._boxWidth/2}
            y=${0}
            width=${this._boxWidth-this._gaugeWidth}
            height=${this._toTranslatedValue(this.instrumentRange)}
            fill="var(--instrument-frame-secondary-color)"
          />

          <g transform="translate(${t}, ${this._boxWidth/4})">
            ${Di({height:this._boxWidth/2,minValue:this._toValue(this.instrumentRange),maxValue:this._toValue(0),width:this._gaugeWidth,scaleWidth:this._scaleWidth},[{min:this._toValue(this.depth),max:this._toValue(0)},{min:this._toValue(this.draft),max:this._toValue(0),fill:o}],{value:this._toValue(this.depth)},{container:"var(--instrument-frame-primary-color)"},{hideContainer:!1,off:!1,priority:this.priority},{primaryTickmarkInterval:this.primaryTickmarkInterval,secondaryTickmarkInterval:this.secondaryTickmarkInterval},this._getAdvice())}
          </g>
          <defs>
            <mask id="hearlineMask">
              <rect x="-200" y="-200" width="400" height="400" fill="white" />
              <line
                y1=${-this._boxWidth/2+5}
                y2=${this._boxWidth/2+5}
                x1=${this._boxWidth/2-this._gaugeWidth}
                x2=${this._boxWidth/2-this._gaugeWidth}
                stroke="black"
                stroke-width="3"
                vector-effect="non-scaling-stroke"
              />
            </mask>
            <mask id="heaveClip">
              <rect
                x=${-this._boxWidth/2}
                y=${-this._boxWidth/2}
                width=${this._boxWidth}
                height=${this._boxWidth}
                rx=${e}
                fill="white"
                vector-effect="non-scaling-stroke"
              />
              <line
                y1=${-this._boxWidth/2}
                y2=${this._boxWidth/2}
                x1=${this._boxWidth/2-this._gaugeWidth}
                x2=${this._boxWidth/2-this._gaugeWidth}
                stroke="black"
                stroke-width="3"
                vector-effect="non-scaling-stroke"
              />
            </mask>
            <pattern
              id="seabedPattern"
              patternUnits="userSpaceOnUse"
              patternTransform="matrix(8 0 0 16 164 294)"
              preserveAspectRatio="none"
              viewBox="0 0 16 32"
              width="1"
              height="1"
            >
              <g id="seabeadInner">
                <rect
                  x="6"
                  y="6"
                  width="4"
                  height="4"
                  fill="var(--instrument-frame-tertiary-color)"
                />
              </g>
              <use xlink:href="#seabeadInner" transform="translate(-16 0)" />
              <use xlink:href="#seabeadInner" transform="translate(-8 16)" />
              <use xlink:href="#seabeadInner" transform="translate(8 16)" />
            </pattern>
          </defs>

          <g mask="url(#heaveClip)">
            <line
              x1=${this._boxWidth/2-this._gaugeWidth}
              x2=${-this._boxWidth/2}
              y1=${0}
              y2=${0}
              stroke="var(--instrument-frame-tertiary-color)"
              stroke-width="1"
              vector-effect="non-scaling-stroke"
            />
            <g
              transform="
              translate(0, ${this._toTranslatedValue(this.draft)-21*r})
            translate(${-this._gaugeWidth/2-80} , -80)
            scale(${r*3} )"
              transform-origin="80 80"
            >
              ${this.vesselImage?mr[this.vesselImage]:f}
            </g>
            ${i}
          </g>
          <g mask="url(#heaveClip)">
            <line
              x1=${this._boxWidth/2-this._gaugeWidth}
              x2=${-this._boxWidth/2}
              y1=${this._toTranslatedValue(this.draft)}
              y2=${this._toTranslatedValue(this.draft)}
              stroke=${o}
              stroke-width="1"
              vector-effect="non-scaling-stroke"
            />
            <line
              x1=${this._boxWidth/2-this._gaugeWidth}
              x2=${-this._boxWidth/2}
              y1=${this._toTranslatedValue(this.depth)}
              y2=${this._toTranslatedValue(this.depth)}
              stroke=${o}
              stroke-width="1"
              vector-effect="non-scaling-stroke"
            />
          </g>
          <path
            mask="url(#hearlineMask)"
            d="M ${this._boxWidth/2} 0
            V -${this._boxWidth/2-e}
             a ${e} ${e} 0 0 0 ${-e} ${-e}
             H ${-this._boxWidth/2+e} 
             a ${e} ${e} 0 0 0 ${-e} ${e}
             V ${this._boxWidth/2-e}
             a ${e} ${e} 0 0 0 ${e} ${e}
             H ${this._boxWidth/2-this._gaugeWidth}"
            stroke="var(--instrument-frame-tertiary-color)"
            fill="none"
            vector-effect="non-scaling-stroke"
          />
        </svg>
      </div>
    `}};he.styles=p`
    * {
      box-sizing: border-box;
    }

    .container {
      position: relative;
      width: 100%;
      height: 100%;
    }

    .container > * {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }
  `;Me([s({type:Number})],he.prototype,"depth",2);Me([s({type:Number})],he.prototype,"draft",2);Me([s({type:Array})],he.prototype,"advice",2);Me([s({type:Number})],he.prototype,"vesselScale",2);Me([s({type:Number})],he.prototype,"instrumentRange",2);Me([s({type:Number})],he.prototype,"primaryTickmarkInterval",2);Me([s({type:Number})],he.prototype,"secondaryTickmarkInterval",2);Me([s({type:String})],he.prototype,"vesselImage",2);Me([s({type:String})],he.prototype,"priority",2);he=Me([h("obc-depth-actual")],he);var Os=Object.defineProperty,Bs=Object.getOwnPropertyDescriptor,ie=(t,e,i,o)=>{for(var r=o>1?void 0:o?Bs(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Os(e,i,r),r};var J=class extends d{constructor(){super(...arguments),this.pitch=0,this.roll=0,this.minAvgPitch=0,this.maxAvgPitch=0,this.minAvgRoll=0,this.maxAvgRoll=0,this.vesselImageFore=Oe.psvFore,this.vesselImageSide=Oe.psvSide,this.maxPitchAdvice=void 0,this.maxRollAdvice=void 0,this.triggerPitchAdvice=!1,this.triggerRollAdvice=!1,this.priority=D.regular,this.priorityElements=["pitch","roll"]}priorityFor(t){return(Array.isArray(this.priorityElements)?this.priorityElements:[]).includes(t)?this.priority:D.regular}needleColor(t){return this.priorityFor(t)===D.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}barColor(t){return this.priorityFor(t)===D.enhanced?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)"}render(){return c`
      <div class="container">
        <svg viewBox="-200 -200 400 400">
          <line
            x1="-150"
            y1="0"
            x2="150"
            y2="0"
            stroke="var(--instrument-frame-tertiary-color)"
          />
        </svg>
        <obc-watch
          .watchCircleType=${$t.double}
          .areas=${[{startAngle:60,endAngle:120,roundOutsideCut:!0,roundInsideCut:!0},{startAngle:240,endAngle:300,roundOutsideCut:!0,roundInsideCut:!0},{startAngle:315,endAngle:45,roundOutsideCut:!0,roundInsideCut:!0},{startAngle:135,endAngle:225,roundOutsideCut:!0,roundInsideCut:!0}]}
          .barAreas=${[{startAngle:this.minAvgRoll,endAngle:this.maxAvgRoll,fillColor:this.barColor("roll")},{startAngle:180+this.minAvgRoll,endAngle:180+this.maxAvgRoll,fillColor:this.barColor("roll")},{startAngle:90+this.minAvgPitch,endAngle:90+this.maxAvgPitch,fillColor:this.barColor("pitch")},{startAngle:270+this.minAvgPitch,endAngle:270+this.maxAvgPitch,fillColor:this.barColor("pitch")}]}
          .needles=${[{angle:this.roll,fillColor:this.needleColor("roll"),strokeColor:"var(--border-silhouette-color)"},{angle:180+this.roll,fillColor:this.needleColor("roll"),strokeColor:"var(--border-silhouette-color)"},{angle:90+this.pitch,fillColor:this.needleColor("pitch"),strokeColor:"var(--border-silhouette-color)"},{angle:270+this.pitch,fillColor:this.needleColor("pitch"),strokeColor:"var(--border-silhouette-color)"}]}
          .vessels=${[{size:Pe.large,vesselImage:this.vesselImageSide,transform:`rotate(${this.pitch}deg)`},{size:Pe.large,vesselImage:this.vesselImageFore,transform:`rotate(${this.roll}deg)`}]}
          .tickmarks=${[{angle:0,type:ee.main},{angle:90,type:ee.main},{angle:180,type:ee.main},{angle:270,type:ee.main}]}
          .advices=${this.advices}
        ></obc-watch>
      </div>
    `}get advices(){let t=[];if(this.maxPitchAdvice!==void 0){let e=this.triggerPitchAdvice?j.triggered:j.regular;t.push({minAngle:60,maxAngle:90-this.maxPitchAdvice,type:ce.caution,state:e,hideMinTickmark:!0}),t.push({minAngle:90+this.maxPitchAdvice,maxAngle:120,type:ce.caution,state:e,hideMaxTickmark:!0}),t.push({minAngle:240,maxAngle:270-this.maxPitchAdvice,type:ce.caution,state:e,hideMinTickmark:!0}),t.push({minAngle:270+this.maxPitchAdvice,maxAngle:300,type:ce.caution,state:e,hideMaxTickmark:!0})}if(this.maxRollAdvice!==void 0){let e=this.triggerRollAdvice?j.triggered:j.regular;t.push({minAngle:-45,maxAngle:-this.maxRollAdvice,type:ce.caution,state:e,hideMinTickmark:!0}),t.push({minAngle:this.maxRollAdvice,maxAngle:45,type:ce.caution,state:e,hideMaxTickmark:!0}),t.push({minAngle:135,maxAngle:180-this.maxRollAdvice,type:ce.caution,state:e,hideMinTickmark:!0}),t.push({minAngle:180+this.maxRollAdvice,maxAngle:225,type:ce.caution,state:e,hideMaxTickmark:!0})}return t}};J.styles=p`
    * {
      box-sizing: border-box;
    }

    .container {
      position: relative;
      width: 100%;
      height: 100%;
    }

    .container > * {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }
  `;ie([s({type:Number})],J.prototype,"pitch",2);ie([s({type:Number})],J.prototype,"roll",2);ie([s({type:Number})],J.prototype,"minAvgPitch",2);ie([s({type:Number})],J.prototype,"maxAvgPitch",2);ie([s({type:Number})],J.prototype,"minAvgRoll",2);ie([s({type:Number})],J.prototype,"maxAvgRoll",2);ie([s({type:String})],J.prototype,"vesselImageFore",2);ie([s({type:String})],J.prototype,"vesselImageSide",2);ie([s({type:Number})],J.prototype,"maxPitchAdvice",2);ie([s({type:Number})],J.prototype,"maxRollAdvice",2);ie([s({type:Boolean})],J.prototype,"triggerPitchAdvice",2);ie([s({type:Boolean})],J.prototype,"triggerRollAdvice",2);ie([s({type:String})],J.prototype,"priority",2);ie([s({type:Array,attribute:!1})],J.prototype,"priorityElements",2);J=ie([h("obc-pitch-roll")],J);var Ii=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  flex: 1;
}

.wrapper {
  height: var(--ui-components-button-touch-target-size);
  width: 100%;
  min-width: var(
    --ui-components-icon-toggle-button-horizontal-item-touch-target-size
  );
  min-height: var(
    --ui-components-toggle-button-toggle-button-item-touch-target-size
  );
  user-select: none;
  padding: 0;
  background: transparent;
  display: flex;
  appearance: none;
  border: none;
  align-items: center;
  justify-content: center;
  position: relative;
}

.wrapper {
            cursor: pointer;
}

.wrapper:focus {
            outline: none;
}

.wrapper .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper:disabled {
            cursor: not-allowed;
}

.wrapper.disabled {
            cursor: not-allowed;
}

.wrapper.activated .visible-wrapper {
      background-color: var(--flat-pressed-background-color);
      border-color: var(--flat-pressed-border-color);
    }

.wrapper.type-flat {
    border: none;
  }

.wrapper.hug-text:not(.icon-text-under) .visible-wrapper {
    width: fit-content;
  }

.wrapper.large:not(.icon-text-under) .visible-wrapper {
    height: 100%;
  }

.visible-wrapper {
  box-sizing: border-box;
  display: flex;
  height: var(--ui-components-toggle-button-toggle-button-item-visual-size);
  min-width: var(
    --ui-components-toggle-button-icon-toggle-button-horizontal-item-touch-target-size
  );
  padding: 0px calc(var(--ui-components-check-button-padding-horizontal) * 2);
  border-radius: var(
    --ui-components-toggle-button-toggle-button-item-border-radius
  );
  width: 100%;
  position: relative;
  align-items: center;
  justify-content: center;
}

.icon {
  color: var(--on-flat-neutral-color);
  width: var(--ui-components-toggle-button-toggle-button-item-icon-size);
  height: var(--ui-components-toggle-button-toggle-button-item-icon-size);
}

.label {
  text-wrap: nowrap;
}

.label-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.wrapper.inline-label .label {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-active-color);
  padding: 0px
    var(--ui-components-toggle-button-toggle-button-item-label-spacing, 8px);
}

:is(.wrapper.selected.type-regular .visible-wrapper) {
            border-color: var(--selected-enabled-border-color);
            background-color: var(--selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--selected-enabled-border-color);
            --base-background-color: var(--selected-enabled-background-color);
}

:is(.wrapper.selected.type-regular .visible-wrapper):focus {
            outline: none;
}

.activated:is(.wrapper.selected.type-regular .visible-wrapper) {
            border-color: var(--selected-activated-border-color);
            background-color: var(--selected-activated-background-color);
            --base-border-color: var(--selected-activated-border-color);
            --base-background-color: var(--selected-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.selected.type-regular .visible-wrapper):hover {
                        border-color: color-mix(in srgb, var(--selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.selected.type-regular .visible-wrapper):active {
            border-color: var(--selected-pressed-border-color);
            background-color: var(--selected-pressed-background-color);
}

:is(.wrapper.selected.type-regular .visible-wrapper):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.selected.type-regular .visible-wrapper):disabled {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.disabled:is(.wrapper.selected.type-regular .visible-wrapper) {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.wrapper.selected.type-regular .icon {
    color: var(--on-selected-active-color);
  }

.wrapper.selected.type-regular .label {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-label-active-font-weight);
    font-size: var(--global-typography-ui-label-active-font-size);
    line-height: var(--global-typography-ui-label-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.wrapper.selected.type-regular.inline-label .label {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-selected-active-color);
  }

.wrapper.selected.type-regular.disabled .visible-wrapper {
      border-color: var(--selected-disabled-border-color);
      background-color: var(--selected-disabled-background-color);
      cursor: not-allowed;
    }

.wrapper.selected.type-regular.disabled .icon,.wrapper.selected.type-regular.disabled.inline-label .label {
      color: var(--on-selected-disabled-color);
    }

.wrapper.selected.type-regular.disabled .label {
      color: var(--on-flat-disabled-color);
    }

:is(.wrapper.selected.type-flat .visible-wrapper) {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

:is(.wrapper.selected.type-flat .visible-wrapper):focus {
            outline: none;
}

.activated:is(.wrapper.selected.type-flat .visible-wrapper) {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.selected.type-flat .visible-wrapper):hover {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.selected.type-flat .visible-wrapper):active {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

:is(.wrapper.selected.type-flat .visible-wrapper):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.selected.type-flat .visible-wrapper):disabled {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.disabled:is(.wrapper.selected.type-flat .visible-wrapper) {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.wrapper.selected.type-flat .icon {
    color: var(--on-amplified-active-color);
  }

.wrapper.selected.type-flat .label {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-label-active-font-weight);
    font-size: var(--global-typography-ui-label-active-font-size);
    line-height: var(--global-typography-ui-label-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-amplified-active-color);
  }

.wrapper.selected.type-flat.inline-label .label {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-amplified-active-color);
  }

.wrapper.selected.type-flat.disabled .visible-wrapper {
      border-color: var(--amplified-disabled-border-color);
      background-color: var(--amplified-disabled-background-color);
      cursor: not-allowed;
    }

.wrapper.selected.type-flat.disabled .icon,.wrapper.selected.type-flat.disabled .label,.wrapper.selected.type-flat.disabled.inline-label .label {
      color: var(--on-amplified-disabled-color);
    }

:is(.wrapper.selected.type-normal .visible-wrapper) {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

:is(.wrapper.selected.type-normal .visible-wrapper):focus {
            outline: none;
}

.activated:is(.wrapper.selected.type-normal .visible-wrapper) {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.selected.type-normal .visible-wrapper):hover {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.selected.type-normal .visible-wrapper):active {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

:is(.wrapper.selected.type-normal .visible-wrapper):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.selected.type-normal .visible-wrapper):disabled {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.disabled:is(.wrapper.selected.type-normal .visible-wrapper) {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.selected.type-normal .icon {
    color: var(--on-normal-neutral-color);
  }

.wrapper.selected.type-normal .label {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-label-active-font-weight);
    font-size: var(--global-typography-ui-label-active-font-size);
    line-height: var(--global-typography-ui-label-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-normal-active-color);
  }

.wrapper.selected.type-normal.inline-label .label {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--on-normal-active-color);
  }

.wrapper.selected.type-normal.disabled .visible-wrapper {
      border-color: var(--normal-disabled-border-color);
      background-color: var(--normal-disabled-background-color);
      cursor: not-allowed;
    }

.wrapper.selected.type-normal.disabled .icon,.wrapper.selected.type-normal.disabled .label,.wrapper.selected.type-normal.disabled.inline-label .label {
      color: var(--on-normal-disabled-color);
    }

.wrapper.selected.icon-text-under .label {
  color: var(--element-active-color);
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-label-active-font-weight);
  font-size: var(--global-typography-ui-label-active-font-size);
  line-height: var(--global-typography-ui-label-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.icon-text-under {
  align-items: flex-start;
  justify-content: flex-start;
  flex-direction: column;
  padding-top: 0;
  height: auto;
  min-height: var(--ui-components-button-touch-target-size);
}

.wrapper.icon-text-under .visible-wrapper {
  margin-top: 0;
  height: var(--ui-components-toggle-button-toggle-button-item-visual-size);
}

.wrapper.icon-text-under .label-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}

.wrapper.icon-text-under .label {
  color: var(--element-active-color, #1a1a1a);
  text-align: center;
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.disabled {
  cursor: not-allowed;
}

.wrapper.disabled .visible-wrapper {
    cursor: not-allowed;
  }

.wrapper.disabled .icon,.wrapper.disabled .label,.wrapper.disabled.inline-label .label,.wrapper.disabled.icon-text-under .label {
    color: var(--on-flat-disabled-color);
  }
`;var Ts=Object.defineProperty,Es=Object.getOwnPropertyDescriptor,xe=(t,e,i,o)=>{for(var r=o>1?void 0:o?Es(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ts(e,i,r),r},ct=(t=>(t.icon="icon",t.text="text",t.iconTextUnder="icon-text-under",t.iconText="text-icon",t))(ct||{}),Je=(t=>(t.flat="flat",t.regular="regular",t.normal="normal",t))(Je||{}),ue=class extends d{constructor(){super(...arguments),this.value="value",this.selected=!1,this.activated=!1,this.type="text",this.variant="regular",this.hugText=!1,this.showDivider=!0,this.disabled=!1,this.large=!1}onClick(t){if(this.disabled){t.preventDefault();return}this.selected||this.dispatchEvent(new CustomEvent("selected",{detail:{value:this.value}}))}render(){let t=this.type==="text"||this.type==="text-icon",e=this.type!=="text",i=this.type!=="icon",o=this.type==="icon-text-under";return c`
      <button
        class=${V({wrapper:!0,selected:this.selected,"inline-label":t,"type-flat":this.variant==="flat","type-regular":this.variant==="regular","type-normal":this.variant==="normal","icon-text-under":o,"hug-text":this.hugText,disabled:this.disabled,activated:this.activated,large:this.large})}
        ?disabled=${this.disabled}
        @click=${this.onClick}
      >
        <div class="visible-wrapper" part="visible-wrapper">
          ${e?c`<div class="icon" part="icon">
                <slot name="icon"></slot>
              </div>`:""}
          ${i&&!o?c`<div class="label"><slot></slot></div>`:""}
        </div>
        ${i&&o?c`<div class="label-container">
              <div class="label"><slot></slot></div>
            </div>`:""}
      </button>
    `}};ue.styles=x(Ii);xe([s({type:String})],ue.prototype,"value",2);xe([s({type:Boolean,reflect:!0})],ue.prototype,"selected",2);xe([s({type:Boolean,reflect:!0})],ue.prototype,"activated",2);xe([s({type:String})],ue.prototype,"type",2);xe([s({type:String})],ue.prototype,"variant",2);xe([s({type:Boolean})],ue.prototype,"hugText",2);xe([s({type:Boolean,reflect:!0})],ue.prototype,"showDivider",2);xe([s({type:Boolean,reflect:!0})],ue.prototype,"disabled",2);xe([s({type:Boolean,reflect:!0})],ue.prototype,"large",2);ue=xe([h("obc-toggle-button-option")],ue);var Ri=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  isolation: isolate;
}

.outer-wrapper {
  box-sizing: border-box;
  width: 100%;
  display: flex;
  align-items: center;
  min-height: var(--ui-components-toggle-button-touch-target-size);
}

.outer-wrapper.hug-text {
    width: fit-content;
  }

.outer-wrapper.icon-text-under .wrapper {
    height: var(--ui-components-toggle-button-toggle-button-item-visual-size);
    align-items: flex-start;
  }

.outer-wrapper.disabled .wrapper {
    background-color: var(--indent-disabled-background-color);
    border-color: var(--indent-disabled-border-color);
  }

.outer-wrapper.large:not(.icon-text-under) .wrapper {
    height: 100%;
  }

.wrapper {
  box-sizing: border-box;
  display: flex;
  position: relative;
  align-items: center;
  height: var(--ui-components-toggle-button-toggle-button-item-visual-size);
  outline: 1px solid var(--indent-enabled-border-color);
  outline-offset: -1px;
  width: 100%;
  background: var(--indent-enabled-background-color);
  flex-shrink: 0;
  border-radius: var(--ui-components-toggle-button-border-radius);
}

.outer-wrapper.flat .wrapper {
  background: none;
  outline: none;
  border: none;
}

.outer-wrapper ::slotted(*:not(:first-child):not([selected]))::before {
    box-sizing: border-box;
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    margin-left: -0.5px;
    margin-top: auto;
    margin-bottom: auto;
    z-index: -1;
    display: block;
    width: 1px;
    border-radius: 1px;
    background: var(--border-divider-color);
    height: var(--ui-components-divider-height-small);
    fill: var(--border-divider-color);
  }

.outer-wrapper.icon-text-under {
  padding: 0;
  align-items: flex-start;
}

::slotted(:not([showdivider]))::before {
  content: none !important;
}

.wrapper ::slotted(*) {
  flex: 1;
}
`;var zs=Object.defineProperty,Ds=Object.getOwnPropertyDescriptor,He=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ds(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&zs(e,i,r),r},ve=class extends d{constructor(){super(...arguments),this.value="",this.type=ct.text,this.variant=Je.regular,this.hugText=!1,this.externalControl=!1,this.disabled=!1,this.large=!1,this._originalDisabledStates=new Map}hasAnyEnabledOption(){return this.disabled?!1:Array.from(this.options).some(t=>!t.disabled)}canSelectOption(t){if(this.disabled)return!1;let e=this.getOptionByValue(t);return e!==null&&!e.disabled}getOptionByValue(t){return Array.from(this.options).find(e=>e.value===t)||null}getFirstSelectableOption(){return this.disabled?null:Array.from(this.options).find(t=>!t.disabled)||null}updateSelection(t,e=!0){let i=this.value;if(!this.hasAnyEnabledOption()){this.options.forEach(o=>{o.selected=o.value===this.value}),this.setNoDivider();return}if(!this.canSelectOption(t)){if(this.value&&this.getOptionByValue(this.value)){this.options.forEach(r=>{r.selected=r.value===this.value}),this.setNoDivider();return}t=this.getFirstSelectableOption()?.value||""}this.value=t,this.options.forEach(o=>{o.selected=o.value===t}),this.setNoDivider(),e&&i!==t&&this.dispatchEvent(new CustomEvent("value",{detail:{value:t,previousValue:i}}))}updateActivated(t){t?this.options.forEach(e=>{e.activated=e.value===t}):this.options.forEach(e=>{e.activated=!1})}setNoDivider(){let t=Array.from(this.options).findIndex(i=>i.selected);if(this.options.forEach(i=>{i.showDivider=!0}),t===-1)return;let e=this.options[t+1];e&&(e.showDivider=!1)}firstUpdated(t){super.firstUpdated(t);let e=Array.from(this.options).map(o=>o.value),i=new Set(e);if(e.length!==i.size&&console.warn("Toggle button group has duplicate values. This may cause unexpected behavior."),this.options.forEach(o=>{this._originalDisabledStates.set(o,o.hasAttribute("disabled")),o.addEventListener("selected",a=>this.handleOptionClick(a)),new MutationObserver(a=>{a.forEach(n=>{n.attributeName==="disabled"&&!o.hasAttribute("data-group-disabled")&&(this._originalDisabledStates.set(o,o.hasAttribute("disabled")),this.handleOptionDisabledChange())})}).observe(o,{attributes:!0,attributeFilter:["disabled"]}),o.type=this.type,o.variant=this.variant,o.hugText=this.hugText,o.large=this.large,this.disabled&&(o.setAttribute("data-group-disabled","true"),o.disabled=!0)}),!this.value||!this.getOptionByValue(this.value)){let o=this.getFirstSelectableOption();o&&this.updateSelection(o.value,!1)}else this.updateSelection(this.value,!1);this.activated&&this.updateActivated(this.activated)}handleOptionDisabledChange(){if(this.getOptionByValue(this.value)?.disabled&&this.hasAnyEnabledOption()){let e=this.getFirstSelectableOption();e&&this.updateSelection(e.value)}}handleOptionClick(t){let{value:e}=t.detail;this.externalControl?this.dispatchEvent(new CustomEvent("value",{detail:{value:e,previousValue:this.value}})):this.updateSelection(e)}willUpdate(t){t.has("value")&&this.updateSelection(this.value),t.has("activated")&&this.updateActivated(this.activated),(t.has("type")||t.has("variant")||t.has("hugText")||t.has("large"))&&this.options.forEach(e=>{e.type=this.type,e.variant=this.variant,e.hugText=this.hugText,e.large=this.large}),t.has("disabled")&&this.options.forEach(e=>{if(this.disabled)e.setAttribute("data-group-disabled","true"),e.disabled=!0;else{e.removeAttribute("data-group-disabled");let i=this._originalDisabledStates.get(e)||!1;e.disabled=i}})}updated(t){if(super.updated(t),this.getOptionByValue(this.value)?.disabled&&this.hasAnyEnabledOption()){let i=this.getFirstSelectableOption();i&&this.updateSelection(i.value)}}render(){let t={"outer-wrapper":!0,flat:this.variant===Je.flat,regular:this.variant===Je.regular,"hug-text":this.hugText,"icon-text-under":this.type===ct.iconTextUnder,disabled:this.disabled,large:this.large};return c`
      <div class=${V(t)}>
        <div class="wrapper">
          <slot></slot>
        </div>
      </div>
    `}};ve.styles=x(Ri);He([s({type:String})],ve.prototype,"value",2);He([s({type:String})],ve.prototype,"activated",2);He([s({type:String})],ve.prototype,"type",2);He([s({type:String})],ve.prototype,"variant",2);He([s({type:Boolean})],ve.prototype,"hugText",2);He([s({type:Boolean})],ve.prototype,"externalControl",2);He([s({type:Boolean,reflect:!0})],ve.prototype,"disabled",2);He([s({type:Boolean,reflect:!0})],ve.prototype,"large",2);He([Xo({selector:"obc-toggle-button-option"})],ve.prototype,"options",2);ve=He([h("obc-toggle-button-group")],ve);var ji=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.card {
  border-radius: 8px;
  background: var(--container-global-color, #fcfcfc);
  /* Shadow/Floating */
  box-shadow: var(--shadow-floating);
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  width: 320px;
  user-select: none;
}

.title-container {
  padding: var(--app-components-system-menu-margin-vertical)
    calc(
      var(--app-components-system-menu-margin-horizontal) +
        var(--app-components-system-menu-padding-horizontal)
    );
}

.title-container h3 {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-semibold);
    font-size: var(--global-typography-ui-overline-font-size);
    line-height: var(--global-typography-ui-overline-line-height);
    letter-spacing: var(--global-typography-ui-overline-letter-spacing);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--element-neutral-color, rgba(0, 0, 0, 0.59));
    margin: 0;
  }

.card.normal .palette .value-label-container {
  padding-top: 0 !important;
}

.content-container {
  padding: var(--app-components-system-menu-padding-vertical)
    var(--app-components-system-menu-margin-vertical);
}

.content-container.palette {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

.content-container.palette.without-link {
      padding-bottom: 24px;
    }

.content-container.palette .value-label-container {
      padding-bottom: 0 !important;
    }

.content-container .value-container {
    display: flex;
    padding: var(--app-components-system-menu-padding-vertical) 0;
    flex-direction: column;
    align-items: center;
    align-self: stretch;
  }

:is(.content-container .value-container) .value-label-container {
      display: flex;
      padding: var(--app-components-system-menu-padding-vertical) 0;
      justify-content: center;
      align-items: center;
      gap: var(--app-components-dimming-menu-label-spacing);
      align-self: stretch;
    }

:is(:is(.content-container .value-container) .value-label-container) .icon {
        width: var(--app-components-dimming-menu-icon-size);
        height: var(--app-components-dimming-menu-icon-size);
        color: var(--instrument-enhanced-secondary-color);
      }

:is(:is(.content-container .value-container) .value-label-container) .label-container {
        display: flex;
        align-items: baseline;
        font-family: var(--global-typography-font-family);
        font-weight: var(
    --global-typography-instrument-value-large-font-weight-active
  );
        font-size: var(--global-typography-instrument-value-large-font-size);
        line-height: var(--global-typography-instrument-value-large-line-height);
        letter-spacing: var(
    --global-typography-instrument-value-large-letter-spacing
  );
        font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
        transition: width 0.1s ease-in-out;
      }

:is(:is(:is(.content-container .value-container) .value-label-container) .label-container) .value {
          color: var(--element-active-color);
        }

:is(:is(:is(.content-container .value-container) .value-label-container) .label-container) .unit {
          font-family: var(--global-typography-font-family);
          font-weight: var(--global-typography-instrument-label-font-weight);
          font-size: var(--global-typography-instrument-label-font-size);
          line-height: var(--global-typography-instrument-label-line-height);
          font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
          color: var(--element-neutral-color);
        }

:is(.content-container .value-container) .value-slider-container {
      width: 100%;
    }

.content-container .icon-button-container {
    display: flex;
    flex-direction: row;
    padding: 0 var(--app-components-system-menu-padding-horizontal);
  }

:is(.content-container .icon-button-container) > obc-button {
      width: 100%;
      display: block;
      z-index: 1;
    }

.disabled:is(:is(.content-container .icon-button-container) > obc-button) {
        z-index: 0;
      }

:is(.content-container .icon-button-container) .btn-icon {
      color: var(--on-normal-neutral-color);
    }

:is(.content-container .icon-button-container) .disabled .btn-icon {
      color: var(--on-normal-disabled-color);
    }

.palette obc-button::part(visible-wrapper) {
  height: 100%;
}

.divider {
  height: 1px;
  align-self: stretch;
  background: var(--border-divider-color);
}

.footer {
  padding: var(--app-components-dimming-menu-padding-vertical)
    var(--app-components-dimming-menu-margin-horizontal);

  padding-top: calc(var(--app-components-dimming-menu-padding-vertical) - 1px);

  border-top: 1px solid var(--border-divider-color);
}

.footer obc-user-button {
    height: auto;
    width: auto;
  }
`;var Ni=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  --_thumb-size: 48px;
  --_thumb-half: 24px;

  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--_thumb-size);

  color: var(--element-neutral-color, #1a1a1a);
}

:host([hugcontainer]) {
  margin-left: -12px;
  margin-right: -12px;
}

.wrapper {
  flex: 1;
  height: var(--_thumb-size);
  position: relative;
}

.wrapper.disabled {
    cursor: not-allowed;
    pointer-events: none;
  }

.wrapper.disabled .track::after {
    background: var(--flat-disabled-background-color);
  }

.wrapper.disabled.enhanced .track {
    background: var(--indent-disabled-background-color);
  }

.wrapper.disabled.enhanced .track::after {
    background: var(--indent-disabled-background-color);
  }

.wrapper.disabled .interactive-track {
    background: var(--selected-disabled-background-color);
    border-color: var(--selected-disabled-background-color);
  }

.wrapper.disabled .thumb {
    background: var(--selected-disabled-background-color);
    border-color: var(--normal-disabled-border-color);
  }

.wrapper.disabled.enhanced .thumb {
    border-color: var(--selected-disabled-border-color);
    background: var(--container-background-color);
  }

.slider {
  position: absolute;
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: var(--_thumb-size);
  margin: 0;
  padding: 0;
  background: none;
}

.slider::-webkit-slider-container {
  position: absolute;
  margin: auto 0;
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  border-radius: 6px;
  cursor: pointer;
}

.no-input :is(.slider::-webkit-slider-container) {
    cursor: default;
  }

.slider::-moz-range-track {
  position: absolute;
  margin: auto 0;
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  height: 40px;
  border-radius: 6px;
  cursor: pointer;
  background: transparent;
  border: none;
}

.no-input :is(.slider::-moz-range-track) {
    cursor: default;
  }

.container-hover {
  position: absolute;
  left: calc(
    var(--_ratio, 0) * (100% - var(--_thumb-size)) + var(--_thumb-size)
  );
  top: 0;
  bottom: 0;
  right: 0;
  cursor: pointer;
}

.no-input .container-hover {
    cursor: default;
  }

.track {
  position: absolute;
  -webkit-appearance: none;
  appearance: none;
  margin: auto 0;
  padding: 0;
  top: 0;
  bottom: 0;
  left: 18px;
  right: 18px;
  height: 4px;
  border-radius: 6px;
  background: var(--border-outline-color);
}

.track::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--flat-enabled-background-color);
    border-radius: 6px;
  }

.enhanced .track {
  height: 32px;
  background: var(--indent-enabled-background-color);
  border: 1px solid var(--indent-enabled-border-color);
}

.normal .track:has(~ .container-hover:hover)::after,
.normal .track:has(~ input:hover)::after {
  background: var(--flat-hover-background-color);
}

.enhanced .track:has(~ .container-hover:hover)::after,
.enhanced .track:has(~ input:hover)::after {
  background-color: var(--indent-hover-background-color);
  border-color: var(--indent-hover-border-color);
}

.normal .track:has(~ .container-hover:active)::after,
.normal .track:has(~ input:active)::after {
  background: var(--flat-pressed-background-color);
}

.enhanced .track:has(~ .container-hover:active)::after,
.enhanced .track:has(~ input:active)::after {
  background-color: var(--indent-pressed-background-color);
  border-color: var(--indent-pressed-border-color);
}

.interactive-track-hover {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  right: calc(
    (1 - var(--_ratio, 0)) * (100% - var(--_thumb-size)) + var(--_thumb-size)
  );
  cursor: pointer;
}

.no-input .interactive-track-hover {
    cursor: default;
  }

.interactive-track {
  position: absolute;
  left: 18px;
  top: 0;
  bottom: 0;
  height: 4px;
  border-radius: 6px;
  right: calc(
    100% - var(--_ratio, 0) * (100% - var(--_thumb-size)) - var(--_thumb-half)
  );
  margin-top: auto;
  margin-bottom: auto;
  background: var(--selected-enabled-background-color);
  border-color: var(--selected-enabled-background-color);
  border-width: 1px;
  border-style: solid;
  pointer-events: none;
}

.enhanced .interactive-track {
  height: 32px;
  right: calc(100% - var(--_ratio, 0) * (100% - var(--_thumb-size)) - 30px);
}

.interactive-track-hover:hover ~ .interactive-track,
input:hover ~ .interactive-track {
  background: var(--selected-hover-background-color);
  border-color: var(--selected-hover-background-color);
}

.interactive-track-hover:active ~ .interactive-track,
input:active ~ .interactive-track {
  background: var(--selected-pressed-background-color);
  border-color: var(--selected-pressed-background-color);
}

/** slider thumb */

input::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  margin: 0;
  padding: 0;
  width: var(--_thumb-size);
  height: var(--_thumb-size);
  background: transparent;
  cursor: grab;
}

input::-moz-range-thumb {
  appearance: none;
  margin: 0;
  padding: 0;
  width: var(--_thumb-size);
  height: var(--_thumb-size);
  background: transparent;
  border: none;
  cursor: grab;
}

.no-input input::-webkit-slider-thumb {
  cursor: default;
}

.no-input input::-moz-range-thumb {
  cursor: default;
}

input:active::-webkit-slider-thumb {
  cursor: grabbing;
}

input:active::-moz-range-thumb {
  cursor: grabbing;
}

.no-input input:active::-webkit-slider-thumb {
  cursor: default;
}

.no-input input:active::-moz-range-thumb {
  cursor: default;
}

.thumb {
  position: absolute;
  top: 0;
  left: calc(var(--_ratio, 0) * (100% - var(--_thumb-size)));
  right: calc((1 - var(--_ratio, 0)) * (100% - var(--_thumb-size)));
  bottom: 0;
  border-radius: 6px;
  border-width: 2px;
  height: 28px;
  width: 12px;
  margin: auto;
  border-style: solid;
  border-color: var(--container-background-color);
  background: var(--selected-enabled-background-color);
  pointer-events: none;
}

:host:has(.no-input) {
  height: 24px;
  margin-left: -8px;
  margin-right: -8px;
}

.no-input .thumb {
    height: 12px;
    width: 12px;
  }

.enhanced .thumb {
  border-width: 4px;
  height: 32px;
  border-color: var(--selected-enabled-background-color);
  background: var(--container-background-color);
}

input:hover ~ .thumb {
  background: var(--selected-hover-background-color);
}

.enhanced input:hover ~ .thumb {
  border-color: var(--selected-hover-background-color);
  background: var(--container-background-color);
}

input:active ~ .thumb {
  background: var(--selected-pressed-background-color);
}

.enhanced input:active ~ .thumb {
  border-color: var(--selected-pressed-background-color);
  background: var(--container-background-color);
}
`;var Is=Object.defineProperty,Rs=Object.getOwnPropertyDescriptor,me=(t,e,i,o)=>{for(var r=o>1?void 0:o?Rs(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Is(e,i,r),r},Vt=(t=>(t.Normal="normal",t.Enhanced="enhanced",t.NoInput="no-input",t))(Vt||{}),se=class extends d{constructor(){super(...arguments),this.value=50,this.min=0,this.max=100,this.stepClick=10,this.variant="normal",this.hasLeftIcon=!1,this.hasRightIcon=!1,this.allowSeeking=!1,this.seekingSpeed=1/3,this.disabled=!1,this.animationFrame=null,this.isMouseDown=!1,this.isTouchActive=!1,this.targetValue=0,this.isDragging=!1,this.animationStartTime=null,this.animationStartValue=0,this.onWindowMouseMove=t=>{this.onMouseMove(t)},this.onWindowMouseUp=()=>{this.onMouseUp()},this.onWindowTouchMove=t=>{this.onTouchMove(t)},this.onWindowTouchEnd=()=>{this.onTouchEnd()}}get ratio(){let t=this.max-this.min;if(!Number.isFinite(t)||t<=0)return 0;let e=(this.value-this.min)/t;return Number.isFinite(e)?Math.max(0,Math.min(1,e)):0}onInput(t){this.value=t,this.dispatchEvent(new CustomEvent("value",{detail:this.value}))}onReduceClick(){this.disabled||this.onInput(Math.max(this.value-this.stepClick,this.min))}onIncreaseClick(){this.disabled||this.onInput(Math.min(this.value+this.stepClick,this.max))}get slider(){return this.renderRoot.querySelector('input[type="range"]')}isClickingThumb(t){let e=this.slider.getBoundingClientRect(),i=e.left+24,o=e.width-48,r=48,a=this.ratio,n=i+o*a,v;return"touches"in t?v=t.touches[0].clientX:v=t.clientX,Math.abs(v-n)<=r/2}onMouseDown(t){this.variant==="no-input"||this.disabled||this.isClickingThumb(t)||(this.isMouseDown=!0,this.updateTargetValue(t),t.preventDefault(),window.addEventListener("mousemove",this.onWindowMouseMove),window.addEventListener("mouseup",this.onWindowMouseUp),this.startAnimation())}onTouchStart(t){this.variant==="no-input"||this.disabled||this.isClickingThumb(t)||(this.isTouchActive=!0,this.updateTargetValue(t),t.preventDefault(),window.addEventListener("touchmove",this.onWindowTouchMove,{passive:!1}),window.addEventListener("touchend",this.onWindowTouchEnd),this.startAnimation())}onMouseMove(t){this.isMouseDown&&this.updateTargetValue(t)}onTouchMove(t){this.isTouchActive&&this.updateTargetValue(t)}onMouseUp(){this.isMouseDown=!1,window.removeEventListener("mousemove",this.onWindowMouseMove),window.removeEventListener("mouseup",this.onWindowMouseUp),this.stopAnimation()}onTouchEnd(){this.isTouchActive=!1,window.removeEventListener("touchmove",this.onWindowTouchMove),window.removeEventListener("touchend",this.onWindowTouchEnd),this.stopAnimation()}updateTargetValue(t){let e=this.slider.getBoundingClientRect(),i=e.left+24,o=e.width-48,a=((t instanceof MouseEvent?t.clientX:t.touches[0].clientX)-i)/o,n=parseFloat(this.slider.min),v=parseFloat(this.slider.max),u=n+(v-n)*a;this.step?this.targetValue=Math.round(u/this.step)*this.step:this.targetValue=u}startAnimation(){this.isDragging=this.allowSeeking,this.animationStartTime=performance.now(),this.animationStartValue=parseFloat(this.slider.value);let t=parseFloat(this.slider.min),e=parseFloat(this.slider.max),i=this.step,o=1/this.seekingSpeed*1e3,r=this.targetValue>this.animationStartValue?1:-1,a=()=>{let n=this.targetValue;if(!this.isDragging){let v=performance.now(),u=v-(this.animationStartTime??v),m=Math.abs(e-t),b=Math.min(u/o,1),g=this.animationStartValue+r*m*b;r>0?(n=i===void 0?g:Math.ceil((g-t)/i)*i+t,n=Math.min(this.targetValue,n)):(n=i===void 0?g:Math.floor((g-t)/i)*i+t,n=Math.max(this.targetValue,n))}parseFloat(this.slider.value)!==n&&(this.slider.value=String(n),this.slider.dispatchEvent(new Event("input"))),r>0&&n<this.targetValue||r<0&&n>this.targetValue?this.animationFrame=requestAnimationFrame(a):(this.isMouseDown||this.isTouchActive)&&(this.animationStartTime=performance.now(),this.animationStartValue=parseFloat(this.slider.value),this.animationFrame=requestAnimationFrame(a),this.isDragging=!0)};this.animationFrame=requestAnimationFrame(a)}stopAnimation(){this.animationFrame!==null&&(cancelAnimationFrame(this.animationFrame),this.animationFrame=null)}render(){return c`
      ${this.hasLeftIcon?c` <obc-icon-button
            ?disabled=${this.disabled}
            @click=${this.onReduceClick}
            variant="normal"
          >
            <slot name="icon-left"></slot>
          </obc-icon-button>`:null}
      <div
        class=${V({wrapper:!0,[this.variant]:!0,disabled:this.disabled})}
        style=${fr({"--_ratio":String(this.ratio)})}
      >
        <div class="track"></div>
        <input
          type="range"
          min=${this.min}
          max=${this.max}
          step=${oe(this.step)}
          .value=${this.value.toString()}
          ?disabled=${this.variant==="no-input"||this.disabled}
          class="slider"
          @input=${t=>{this.value=Number(t.target.value),this.dispatchEvent(new CustomEvent("value",{detail:this.value}))}}
          @mousedown=${this.onMouseDown}
          @touchstart=${this.onTouchStart}
          @mousemove=${this.onMouseMove}
          @touchmove=${this.onTouchMove}
          @mouseup=${this.onMouseUp}
          @touchend=${this.onTouchEnd}
        />
        <div
          class="interactive-track-hover"
          @mousedown=${this.onMouseDown}
          @touchstart=${this.onTouchStart}
          @mousemove=${this.onMouseMove}
          @touchmove=${this.onTouchMove}
          @mouseup=${this.onMouseUp}
          @touchend=${this.onTouchEnd}
        ></div>
        <div
          class="container-hover"
          @mousedown=${this.onMouseDown}
          @touchstart=${this.onTouchStart}
          @mousemove=${this.onMouseMove}
          @touchmove=${this.onTouchMove}
          @mouseup=${this.onMouseUp}
          @touchend=${this.onTouchEnd}
        ></div>
        <div class="interactive-track"></div>
        <div class="thumb"></div>
      </div>
      ${this.hasRightIcon?c`<obc-icon-button
            ?disabled=${this.disabled}
            @click=${this.onIncreaseClick}
            variant="normal"
          >
            <slot name="icon-right"></slot>
          </obc-icon-button>`:null}
    `}};se.styles=x(Ni);me([s({type:Number})],se.prototype,"value",2);me([s({type:Number})],se.prototype,"min",2);me([s({type:Number})],se.prototype,"max",2);me([s({type:Number})],se.prototype,"step",2);me([s({type:Number})],se.prototype,"stepClick",2);me([s({type:String})],se.prototype,"variant",2);me([s({type:Boolean})],se.prototype,"hasLeftIcon",2);me([s({type:Boolean})],se.prototype,"hasRightIcon",2);me([s({type:Boolean})],se.prototype,"allowSeeking",2);me([s({type:Number})],se.prototype,"seekingSpeed",2);me([s({type:Boolean})],se.prototype,"disabled",2);se=me([h("obc-slider")],se);var Fi=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

label {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  height: var(--ui-components-toggle-switch-item-touch-target-size-two-story);
  padding: 0px var(--ui-components-toggle-switch-item-padding-horizontal);
  flex: 1 0 0;

  color: var(--element-active-color);
  cursor: pointer;
  user-select: none;
}

label.has-description .icon-label-container {
    display: flex;
    align-items: center;
    flex: 1 0 0;
  }

label .label {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-body-font-weight);
    font-size: var(--global-typography-ui-body-font-size);
    line-height: var(--global-typography-ui-body-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

label .description {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
    color: var(--element-neutral-color);
    overflow: hidden;
  }

label .icon-label-container {
    display: flex;
    align-items: center;
    flex: 1 0 0;
  }

label .label-container {
    display: flex;
    padding: 0px var(--ui-components-toggle-switch-item-label-spacing);
    align-items: center;
    flex: 1 0 0;
  }

label.has-description .label-container {
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
  }

label .presenter {
    box-sizing: border-box;
    width: var(--ui-components-toggle-switch-selection-width);
    height: var(--ui-components-toggle-switch-selection-height);
    padding: 0px var(--ui-components-toggle-switch-selection-padding);
    flex-shrink: 0;
    border-radius: var(--ui-components-toggle-switch-item-border-radius);

    background: var(--indent-enabled-background-color, rgba(0, 0, 0, 0.05));
    border: solid 1px var(--element-inactive-color, rgba(0, 0, 0, 0.42));
    user-select: none;

    display: flex;
    position: relative;
    align-items: center;

    /* Add transition for smooth background and border color changes */
    transition:
      background-color 0.3s ease,
      border-color 0.3s ease,
      box-shadow 0.15s ease;
  }

:is(label .presenter):hover {
      background: var(--indent-hover-background-color, rgba(0, 0, 0, 0.1));
    }

:is(label .presenter):active {
      background: var(--indent-pressed-background-color, rgba(0, 0, 0, 0.16));
    }

:is(label .presenter):has(:focus-visible) {
      /* Remove the original border when focused */
      border: 1px solid transparent;

      /* Ensure the focus styling works with the proper border radius */
      border-radius: var(
        --global-border-radius-border-radius-round,
        var(--ui-components-toggle-switch-item-border-radius)
      );

      /* Create the double border effect with proper spacing */
      box-shadow: 
        /* Inner border (1px) */
        0 0 0 1px var(--container-global-color, #fff),
        /* Outer border (variable width) */ 0 0 0
          calc(1px + var(--global-size-spacing-border-weight-focusframe, 2px))
          var(--border-focus-color, #007bff);

      /* Remove default outline */
      outline: none;

      /* Ensure the element is positioned to accommodate the box-shadow */
      position: relative;
      z-index: 1;
    }

label.disabled * {
    color: var(--element-disabled-color);
    cursor: not-allowed;
  }

label.disabled {
    cursor: not-allowed;
  }

:is(label.disabled .presenter) {
            border-color: var(--disabled-enabled-border-color);
            background-color: var(--disabled-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--disabled-enabled-border-color);
            --base-background-color: var(--disabled-enabled-background-color);
}

:is(label.disabled .presenter):focus {
            outline: none;
}

.activated:is(label.disabled .presenter) {
            border-color: var(--disabled-activated-border-color);
            background-color: var(--disabled-activated-background-color);
            --base-border-color: var(--disabled-activated-border-color);
            --base-background-color: var(--disabled-activated-background-color);
}

@media (hover:hover) {

:is(label.disabled .presenter):hover {
                        border-color: color-mix(in srgb, var(--disabled-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--disabled-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(label.disabled .presenter):active {
            border-color: var(--disabled-pressed-border-color);
            background-color: var(--disabled-pressed-background-color);
}

:is(label.disabled .presenter):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(label.disabled .presenter):disabled {
            border-color: var(--disabled-disabled-border-color);
            background-color: var(--disabled-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-disabled-disabled-color) !important;
}

.disabled:is(label.disabled .presenter) {
            border-color: var(--disabled-disabled-border-color);
            background-color: var(--disabled-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-disabled-disabled-color) !important;
}

label.disabled .knob {
      background-color: var(--element-disabled-color);
    }

label.checked .label {
      font-family: var(--font-family-main);
      font-weight: var(--font-weight-bold);
      font-size: var(--global-typography-ui-body-active-font-size);
      line-height: var(--global-typography-ui-body-active-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    }

:is(label.checked .presenter) {
            border-color: var(--selected-enabled-border-color);
            background-color: var(--selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--selected-enabled-border-color);
            --base-background-color: var(--selected-enabled-background-color);
}

:is(label.checked .presenter):focus {
            outline: none;
}

.activated:is(label.checked .presenter) {
            border-color: var(--selected-activated-border-color);
            background-color: var(--selected-activated-background-color);
            --base-border-color: var(--selected-activated-border-color);
            --base-background-color: var(--selected-activated-background-color);
}

@media (hover:hover) {

:is(label.checked .presenter):hover {
                        border-color: color-mix(in srgb, var(--selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(label.checked .presenter):active {
            border-color: var(--selected-pressed-border-color);
            background-color: var(--selected-pressed-background-color);
}

:is(label.checked .presenter):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(label.checked .presenter):disabled {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.disabled:is(label.checked .presenter) {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

label.checked.disabled .presenter {
        border-color: var(--selected-disabled-border-color);
        background-color: var(--selected-disabled-background-color);
        cursor: not-allowed;
      }

label.checked.disabled .knob {
        background-color: var(--on-selected-disabled-color);
      }

.icon-container {
  width: var(--ui-components-toggle-switch-item-icon-size);
  height: var(--ui-components-toggle-switch-item-icon-size);
  color: var(--element-neutral-color);
}

.switch {
  padding: var(--global-size-spacing-border-weight-focusframe, 2px);
  overflow: visible;
}

input {
  position: absolute;
  height: var(--ui-components-toggle-switch-touch-target);
  width: var(--ui-components-toggle-switch-selection-width);
  top: 0;
  bottom: 0;
  right: -1px;
  left: -1px;
  opacity: 0;
  margin: auto;
  cursor: pointer;
}

.knob {
  width: var(--ui-components-toggle-switch-thumb-size);
  height: var(--ui-components-toggle-switch-thumb-size);
  flex-shrink: 0;
  fill: var(--on-selected-active-color);
  border-radius: 50%;

  background: var(--element-neutral-color, rgba(0, 0, 0, 0.59));

  /* Add transition for smooth knob movement and color change */
  transition:
    transform 0.3s ease,
    background-color 0.3s ease;
}

.checked .knob {
    background: var(--on-selected-active-color, #fff);
    /* Move knob to the right edge, matching the original flex-end position */
    transform: translateX(
      calc(
        var(--ui-components-toggle-switch-selection-width) -
          var(--ui-components-toggle-switch-thumb-size) -
          (2 * var(--ui-components-toggle-switch-selection-padding))
      )
    );
  }

.bottom-divider {
  width: 100%;
  height: 1px;
  position: absolute;
  bottom: -1px;
  border-radius: 1px;
  background: var(--border-divider-color);
}
`;var js=Object.defineProperty,Ns=Object.getOwnPropertyDescriptor,Be=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ns(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&js(e,i,r),r},Ce=class extends d{constructor(){super(...arguments),this.label="Label",this.checked=!1,this.disabled=!1,this.hasDescription=!1,this.description="",this.hasBottomDivider=!1,this.hasIcon=!1,this.externalControl=!1}_tryChange(t){if(this.disabled){t.preventDefault();return}let e=!this.checked;this.externalControl||(this.checked=e),t.stopPropagation(),this.dispatchEvent(new CustomEvent("input",{detail:{checked:e}})),this.externalControl&&(t.target.checked=this.checked)}render(){return c`
      <label
        class=${V({checked:this.checked,disabled:this.disabled,"has-description":this.hasDescription})}
      >
        <div class="icon-label-container">
          ${this.hasIcon?c`<div class="icon-container"><slot name="icon"></slot></div>`:f}
          <div class="label-container">
            <span class="label">${this.label}</span>
            ${this.hasDescription?c`<span class="description">${this.description}</span>`:f}
          </div>
        </div>
        <div class="switch">
          <div class="presenter ${V({checked:this.checked})}">
            <div class="knob"></div>
            <input
              type="checkbox"
              .checked=${this.checked}
              ?disabled=${this.disabled}
              @input=${this._tryChange}
            />
          </div>
        </div>
        ${this.hasBottomDivider?c`<div class="bottom-divider"></div>`:f}
      </label>
    `}};Ce.styles=x(Fi);Be([s({type:String})],Ce.prototype,"label",2);Be([s({type:Boolean})],Ce.prototype,"checked",2);Be([s({type:Boolean})],Ce.prototype,"disabled",2);Be([s({type:Boolean})],Ce.prototype,"hasDescription",2);Be([s({type:String})],Ce.prototype,"description",2);Be([s({type:Boolean})],Ce.prototype,"hasBottomDivider",2);Be([s({type:Boolean})],Ce.prototype,"hasIcon",2);Be([s({type:Boolean})],Ce.prototype,"externalControl",2);Ce=Be([h("obc-toggle-switch")],Ce);var Fs=Object.defineProperty,Us=Object.getOwnPropertyDescriptor,Ui=(t,e,i,o)=>{for(var r=o>1?void 0:o?Us(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Fs(e,i,r),r},Lr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M16.9498 15.5355L15.5355 16.9497L16.9498 18.364L18.364 16.9497L16.9498 15.5355Z" fill="currentColor"/>
<path d="M13 18V20H11V18H13Z" fill="currentColor"/>
<path d="M8.46447 16.9498L7.05025 15.5355L5.63604 16.9498L7.05025 18.364L8.46447 16.9498Z" fill="currentColor"/>
<path d="M4 13V11H6L6 13H4Z" fill="currentColor"/>
<path d="M7.05025 5.63604L5.63604 7.05025L7.05025 8.46446L8.46447 7.05025L7.05025 5.63604Z" fill="currentColor"/>
<path d="M11 4H13V6H11V4Z" fill="currentColor"/>
<path d="M18.364 7.05025L16.9497 5.63604L15.5355 7.05025L16.9497 8.46447L18.364 7.05025Z" fill="currentColor"/>
<path d="M18 11H20V13H18V11Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 13C12.5523 13 13 12.5523 13 12C13 11.4477 12.5523 11 12 11C11.4477 11 11 11.4477 11 12C11 12.5523 11.4477 13 12 13ZM12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M16.9498 15.5355L15.5355 16.9497L16.9498 18.364L18.364 16.9497L16.9498 15.5355Z" style="fill: var(--element-active-color)"/>
<path d="M13 18V20H11V18H13Z" style="fill: var(--element-active-color)"/>
<path d="M8.46447 16.9498L7.05025 15.5355L5.63604 16.9498L7.05025 18.364L8.46447 16.9498Z" style="fill: var(--element-active-color)"/>
<path d="M4 13V11H6L6 13H4Z" style="fill: var(--element-active-color)"/>
<path d="M7.05025 5.63604L5.63604 7.05025L7.05025 8.46446L8.46447 7.05025L7.05025 5.63604Z" style="fill: var(--element-active-color)"/>
<path d="M11 4H13V6H11V4Z" style="fill: var(--element-active-color)"/>
<path d="M18.364 7.05025L16.9497 5.63604L15.5355 7.05025L16.9497 8.46447L18.364 7.05025Z" style="fill: var(--element-active-color)"/>
<path d="M18 11H20V13H18V11Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 13C12.5523 13 13 12.5523 13 12C13 11.4477 12.5523 11 12 11C11.4477 11 11 11.4477 11 12C11 12.5523 11.4477 13 12 13ZM12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Lr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ui([s({type:Boolean})],Lr.prototype,"useCssColor",2);Lr=Ui([h("obi-display-brilliance-low")],Lr);var Ws=Object.defineProperty,Gs=Object.getOwnPropertyDescriptor,Wi=(t,e,i,o)=>{for(var r=o>1?void 0:o?Gs(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ws(e,i,r),r},kr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.8331 9.17621C14.83 9.17312 14.8269 9.17002 14.8238 9.16694C14.1003 8.4458 13.1022 8 12 8C10.8978 8 9.89964 8.44583 9.17615 9.167C9.1731 9.17005 9.17005 9.1731 9.167 9.17615C8.44583 9.89964 8 10.8978 8 12C8 14.2091 9.79086 16 12 16C14.2091 16 16 14.2091 16 12C16 10.8978 15.5542 9.8997 14.8331 9.17621ZM12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14ZM18.364 4.22182L19.7782 5.63604L16.9497 8.46447L16.237 7.75175L15.5355 7.05025L18.364 4.22182ZM4.22183 5.63604L5.63605 4.22183L8.46447 7.05025L7.76316 7.75157L7.75175 7.76298L7.05026 8.46447L4.22183 5.63604ZM7.05025 15.5355L8.46446 16.9498L5.63603 19.7782L4.22182 18.364L7.05025 15.5355ZM16.9498 15.5355L19.7782 18.364L18.364 19.7782L15.5355 16.9497L16.9498 15.5355ZM11 2H13V6H11V2ZM2 13V11H6V13H2ZM13 22H11V18H13V22ZM22 11V13H18V11H22Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.8331 9.17621C14.83 9.17312 14.8269 9.17002 14.8238 9.16694C14.1003 8.4458 13.1022 8 12 8C10.8978 8 9.89964 8.44583 9.17615 9.167C9.1731 9.17005 9.17005 9.1731 9.167 9.17615C8.44583 9.89964 8 10.8978 8 12C8 14.2091 9.79086 16 12 16C14.2091 16 16 14.2091 16 12C16 10.8978 15.5542 9.8997 14.8331 9.17621ZM12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14ZM18.364 4.22182L19.7782 5.63604L16.9497 8.46447L16.237 7.75175L15.5355 7.05025L18.364 4.22182ZM4.22183 5.63604L5.63605 4.22183L8.46447 7.05025L7.76316 7.75157L7.75175 7.76298L7.05026 8.46447L4.22183 5.63604ZM7.05025 15.5355L8.46446 16.9498L5.63603 19.7782L4.22182 18.364L7.05025 15.5355ZM16.9498 15.5355L19.7782 18.364L18.364 19.7782L15.5355 16.9497L16.9498 15.5355ZM11 2H13V6H11V2ZM2 13V11H6V13H2ZM13 22H11V18H13V22ZM22 11V13H18V11H22Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};kr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Wi([s({type:Boolean})],kr.prototype,"useCssColor",2);kr=Wi([h("obi-display-brilliance-proposal")],kr);var qs=Object.defineProperty,Xs=Object.getOwnPropertyDescriptor,Gi=(t,e,i,o)=>{for(var r=o>1?void 0:o?Xs(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&qs(e,i,r),r},Mr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21C9.5 21 7.375 20.125 5.625 18.375C3.875 16.625 3 14.5 3 12C3 9.5 3.875 7.375 5.625 5.625C7.375 3.875 9.5 3 12 3C12.2333 3 12.4625 3.00833 12.6875 3.025C12.9125 3.04167 13.1333 3.06667 13.35 3.1C12.6667 3.58333 12.1208 4.2125 11.7125 4.9875C11.3042 5.7625 11.1 6.6 11.1 7.5C11.1 9 11.625 10.275 12.675 11.325C13.725 12.375 15 12.9 16.5 12.9C17.4167 12.9 18.2583 12.6958 19.025 12.2875C19.7917 11.8792 20.4167 11.3333 20.9 10.65C20.9333 10.8667 20.9583 11.0875 20.975 11.3125C20.9917 11.5375 21 11.7667 21 12C21 14.5 20.125 16.625 18.375 18.375C16.625 20.125 14.5 21 12 21ZM12 19C13.4667 19 14.7833 18.5958 15.95 17.7875C17.1167 16.9792 17.9667 15.925 18.5 14.625C18.1667 14.7083 17.8333 14.775 17.5 14.825C17.1667 14.875 16.8333 14.9 16.5 14.9C14.45 14.9 12.7042 14.1792 11.2625 12.7375C9.82083 11.2958 9.1 9.55 9.1 7.5C9.1 7.16667 9.125 6.83333 9.175 6.5C9.225 6.16667 9.29167 5.83333 9.375 5.5C8.075 6.03333 7.02083 6.88333 6.2125 8.05C5.40417 9.21667 5 10.5333 5 12C5 13.9333 5.68333 15.5833 7.05 16.95C8.41667 18.3167 10.0667 19 12 19Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21C9.5 21 7.375 20.125 5.625 18.375C3.875 16.625 3 14.5 3 12C3 9.5 3.875 7.375 5.625 5.625C7.375 3.875 9.5 3 12 3C12.2333 3 12.4625 3.00833 12.6875 3.025C12.9125 3.04167 13.1333 3.06667 13.35 3.1C12.6667 3.58333 12.1208 4.2125 11.7125 4.9875C11.3042 5.7625 11.1 6.6 11.1 7.5C11.1 9 11.625 10.275 12.675 11.325C13.725 12.375 15 12.9 16.5 12.9C17.4167 12.9 18.2583 12.6958 19.025 12.2875C19.7917 11.8792 20.4167 11.3333 20.9 10.65C20.9333 10.8667 20.9583 11.0875 20.975 11.3125C20.9917 11.5375 21 11.7667 21 12C21 14.5 20.125 16.625 18.375 18.375C16.625 20.125 14.5 21 12 21ZM12 19C13.4667 19 14.7833 18.5958 15.95 17.7875C17.1167 16.9792 17.9667 15.925 18.5 14.625C18.1667 14.7083 17.8333 14.775 17.5 14.825C17.1667 14.875 16.8333 14.9 16.5 14.9C14.45 14.9 12.7042 14.1792 11.2625 12.7375C9.82083 11.2958 9.1 9.55 9.1 7.5C9.1 7.16667 9.125 6.83333 9.175 6.5C9.225 6.16667 9.29167 5.83333 9.375 5.5C8.075 6.03333 7.02083 6.88333 6.2125 8.05C5.40417 9.21667 5 10.5333 5 12C5 13.9333 5.68333 15.5833 7.05 16.95C8.41667 18.3167 10.0667 19 12 19Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Mr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Gi([s({type:Boolean})],Mr.prototype,"useCssColor",2);Mr=Gi([h("obi-palette-night")],Mr);var Ys=Object.defineProperty,Js=Object.getOwnPropertyDescriptor,qi=(t,e,i,o)=>{for(var r=o>1?void 0:o?Js(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ys(e,i,r),r},xr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.5529 3.75275C11.7695 3.24908 12.4805 3.24908 12.6971 3.75276L13.8662 6.47216C14.0151 6.81843 14.4328 6.95476 14.7559 6.76251L17.2931 5.2527C17.763 4.97306 18.3383 5.39286 18.2187 5.92818L17.5732 8.81846C17.491 9.18649 17.7491 9.5434 18.123 9.57861L21.0592 9.85509C21.603 9.9063 21.8228 10.5855 21.4128 10.948L19.1991 12.9052C19.1278 12.9683 19.0745 13.0436 19.0393 13.125H21C21.4142 13.125 21.75 13.4608 21.75 13.875C21.75 14.2892 21.4142 14.625 21 14.625H3C2.58579 14.625 2.25 14.2892 2.25 13.875C2.25 13.4608 2.58579 13.125 3 13.125H5.21069C5.17546 13.0436 5.12219 12.9683 5.05087 12.9052L2.83724 10.948C2.42724 10.5855 2.64697 9.9063 3.1908 9.85509L6.12699 9.57861C6.50087 9.5434 6.75903 9.18649 6.67683 8.81846L6.0313 5.92818C5.91173 5.39286 6.48698 4.97306 6.95691 5.2527L9.49414 6.76251C9.81722 6.95476 10.2349 6.81843 10.3838 6.47216L11.5529 3.75275ZM7.13114 13.125H17.1189C16.9886 10.4797 14.8026 8.375 12.125 8.375C9.44741 8.375 7.2614 10.4797 7.13114 13.125Z" fill="currentColor"/>
<path d="M7.5 15.75C7.08579 15.75 6.75 16.0858 6.75 16.5C6.75 16.9142 7.08579 17.25 7.5 17.25H16.5C16.9142 17.25 17.25 16.9142 17.25 16.5C17.25 16.0858 16.9142 15.75 16.5 15.75H7.5Z" fill="currentColor"/>
<path d="M13.875 19.25C13.875 19.6642 13.5392 20 13.125 20H12H10.875C10.4608 20 10.125 19.6642 10.125 19.25C10.125 18.8358 10.4608 18.5 10.875 18.5H12H13.125C13.5392 18.5 13.875 18.8358 13.875 19.25Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.5529 3.75275C11.7695 3.24908 12.4805 3.24908 12.6971 3.75276L13.8662 6.47216C14.0151 6.81843 14.4328 6.95476 14.7559 6.76251L17.2931 5.2527C17.763 4.97306 18.3383 5.39286 18.2187 5.92818L17.5732 8.81846C17.491 9.18649 17.7491 9.5434 18.123 9.57861L21.0592 9.85509C21.603 9.9063 21.8228 10.5855 21.4128 10.948L19.1991 12.9052C19.1278 12.9683 19.0745 13.0436 19.0393 13.125H21C21.4142 13.125 21.75 13.4608 21.75 13.875C21.75 14.2892 21.4142 14.625 21 14.625H3C2.58579 14.625 2.25 14.2892 2.25 13.875C2.25 13.4608 2.58579 13.125 3 13.125H5.21069C5.17546 13.0436 5.12219 12.9683 5.05087 12.9052L2.83724 10.948C2.42724 10.5855 2.64697 9.9063 3.1908 9.85509L6.12699 9.57861C6.50087 9.5434 6.75903 9.18649 6.67683 8.81846L6.0313 5.92818C5.91173 5.39286 6.48698 4.97306 6.95691 5.2527L9.49414 6.76251C9.81722 6.95476 10.2349 6.81843 10.3838 6.47216L11.5529 3.75275ZM7.13114 13.125H17.1189C16.9886 10.4797 14.8026 8.375 12.125 8.375C9.44741 8.375 7.2614 10.4797 7.13114 13.125Z" style="fill: var(--element-active-color)"/>
<path d="M7.5 15.75C7.08579 15.75 6.75 16.0858 6.75 16.5C6.75 16.9142 7.08579 17.25 7.5 17.25H16.5C16.9142 17.25 17.25 16.9142 17.25 16.5C17.25 16.0858 16.9142 15.75 16.5 15.75H7.5Z" style="fill: var(--element-active-color)"/>
<path d="M13.875 19.25C13.875 19.6642 13.5392 20 13.125 20H12H10.875C10.4608 20 10.125 19.6642 10.125 19.25C10.125 18.8358 10.4608 18.5 10.875 18.5H12H13.125C13.5392 18.5 13.875 18.8358 13.875 19.25Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};xr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;qi([s({type:Boolean})],xr.prototype,"useCssColor",2);xr=qi([h("obi-palette-dusk")],xr);var Qs=Object.defineProperty,Ks=Object.getOwnPropertyDescriptor,Xi=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ks(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Qs(e,i,r),r},Hr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.4178 2.66892C14.7789 2.25636 15.4554 2.47526 15.5064 3.02113L15.7816 5.96838C15.8166 6.34367 16.1721 6.60197 16.5386 6.51851L19.4174 5.8631C19.9506 5.74171 20.3687 6.3182 20.0902 6.79072L18.5862 9.34191C18.3947 9.66677 18.5305 10.0858 18.8753 10.2344L21.5838 11.4014C22.0855 11.6175 22.0854 12.3314 21.5838 12.5501L19.2437 13.5701C19.9738 14.2507 20.5123 15.1503 20.7626 16.1622C21.9582 16.6967 22.7499 17.9449 22.7499 19.3243C22.7499 21.1817 21.3013 22.75 19.4588 22.75H9.62935C8.73882 22.75 7.89257 22.3876 7.27532 21.7385C6.61858 21.085 6.27173 20.2054 6.25014 19.2667L6.24994 19.2581V19.212C6.24994 18.6736 6.37017 18.152 6.59526 17.6786L4.5824 18.1369C4.04921 18.2582 3.63113 17.6818 3.90968 17.2092L5.41363 14.658C5.60514 14.3332 5.46938 13.9141 5.12449 13.7655L2.41601 12.5986C1.91436 12.3825 1.9144 11.6686 2.41608 11.4499L5.12472 10.2692C5.46962 10.1189 5.60543 9.69915 5.41397 9.37526L3.91034 6.83168C3.63185 6.36057 4.05 5.78196 4.58318 5.90066L7.4619 6.54149C7.82846 6.62309 8.18396 6.36299 8.21905 5.98753L8.49462 3.03888C8.54566 2.49275 9.2222 2.27043 9.58323 2.68116L11.5324 4.89872C11.7807 5.18109 12.2201 5.17998 12.4683 4.89635L14.4178 2.66892ZM8.77567 15.8232C9.0014 15.7627 9.23504 15.7262 9.47374 15.7151C9.91656 15.02 10.6813 14.5702 11.5529 14.5702C11.6374 14.5702 11.7229 14.5744 11.8091 14.5835C12.7056 13.1529 14.2426 12.25 15.947 12.25C16.3039 12.25 16.652 12.29 16.9877 12.3658C17.1542 10.1198 15.7772 7.96694 13.5391 7.2428C10.9118 6.39271 8.09283 7.83343 7.24274 10.4608C6.59862 12.4515 7.26972 14.5523 8.77567 15.8232ZM12.8665 15.771C13.4558 14.5213 14.6481 13.75 15.947 13.75C17.6096 13.75 19.0881 15.057 19.371 16.8409L19.4468 17.3191L19.9138 17.4469C20.6575 17.6504 21.2499 18.4014 21.2499 19.3243C21.2499 20.4233 20.4045 21.25 19.4588 21.25H9.62935C9.14786 21.25 8.69223 21.0546 8.35732 20.6995L8.34813 20.6898L8.3386 20.6804C7.9796 20.326 7.7653 19.8279 7.74994 19.2403V19.212C7.74994 18.6904 7.94322 18.1961 8.2958 17.8083C8.65036 17.419 9.1208 17.2115 9.62936 17.2115C9.73976 17.2115 9.76618 17.213 9.79884 17.2188L10.4228 17.329L10.6357 16.7323C10.7806 16.3265 11.1414 16.0702 11.5529 16.0702C11.6726 16.0702 11.7795 16.0905 11.8851 16.1372L12.5544 16.4329L12.8665 15.771Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.4178 2.66892C14.7789 2.25636 15.4554 2.47526 15.5064 3.02113L15.7816 5.96838C15.8166 6.34367 16.1721 6.60197 16.5386 6.51851L19.4174 5.8631C19.9506 5.74171 20.3687 6.3182 20.0902 6.79072L18.5862 9.34191C18.3947 9.66677 18.5305 10.0858 18.8753 10.2344L21.5838 11.4014C22.0855 11.6175 22.0854 12.3314 21.5838 12.5501L19.2437 13.5701C19.9738 14.2507 20.5123 15.1503 20.7626 16.1622C21.9582 16.6967 22.7499 17.9449 22.7499 19.3243C22.7499 21.1817 21.3013 22.75 19.4588 22.75H9.62935C8.73882 22.75 7.89257 22.3876 7.27532 21.7385C6.61858 21.085 6.27173 20.2054 6.25014 19.2667L6.24994 19.2581V19.212C6.24994 18.6736 6.37017 18.152 6.59526 17.6786L4.5824 18.1369C4.04921 18.2582 3.63113 17.6818 3.90968 17.2092L5.41363 14.658C5.60514 14.3332 5.46938 13.9141 5.12449 13.7655L2.41601 12.5986C1.91436 12.3825 1.9144 11.6686 2.41608 11.4499L5.12472 10.2692C5.46962 10.1189 5.60543 9.69915 5.41397 9.37526L3.91034 6.83168C3.63185 6.36057 4.05 5.78196 4.58318 5.90066L7.4619 6.54149C7.82846 6.62309 8.18396 6.36299 8.21905 5.98753L8.49462 3.03888C8.54566 2.49275 9.2222 2.27043 9.58323 2.68116L11.5324 4.89872C11.7807 5.18109 12.2201 5.17998 12.4683 4.89635L14.4178 2.66892ZM8.77567 15.8232C9.0014 15.7627 9.23504 15.7262 9.47374 15.7151C9.91656 15.02 10.6813 14.5702 11.5529 14.5702C11.6374 14.5702 11.7229 14.5744 11.8091 14.5835C12.7056 13.1529 14.2426 12.25 15.947 12.25C16.3039 12.25 16.652 12.29 16.9877 12.3658C17.1542 10.1198 15.7772 7.96694 13.5391 7.2428C10.9118 6.39271 8.09283 7.83343 7.24274 10.4608C6.59862 12.4515 7.26972 14.5523 8.77567 15.8232ZM12.8665 15.771C13.4558 14.5213 14.6481 13.75 15.947 13.75C17.6096 13.75 19.0881 15.057 19.371 16.8409L19.4468 17.3191L19.9138 17.4469C20.6575 17.6504 21.2499 18.4014 21.2499 19.3243C21.2499 20.4233 20.4045 21.25 19.4588 21.25H9.62935C9.14786 21.25 8.69223 21.0546 8.35732 20.6995L8.34813 20.6898L8.3386 20.6804C7.9796 20.326 7.7653 19.8279 7.74994 19.2403V19.212C7.74994 18.6904 7.94322 18.1961 8.2958 17.8083C8.65036 17.419 9.1208 17.2115 9.62936 17.2115C9.73976 17.2115 9.76618 17.213 9.79884 17.2188L10.4228 17.329L10.6357 16.7323C10.7806 16.3265 11.1414 16.0702 11.5529 16.0702C11.6726 16.0702 11.7795 16.0905 11.8851 16.1372L12.5544 16.4329L12.8665 15.771Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Hr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Xi([s({type:Boolean})],Hr.prototype,"useCssColor",2);Hr=Xi([h("obi-palette-day")],Hr);var el=Object.defineProperty,tl=Object.getOwnPropertyDescriptor,Yi=(t,e,i,o)=>{for(var r=o>1?void 0:o?tl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&el(e,i,r),r},$r=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.4279 2.37775C11.6445 1.87408 12.3555 1.87408 12.5721 2.37776L13.7412 5.09716C13.8901 5.44343 14.3078 5.57976 14.6309 5.38751L17.1681 3.8777C17.638 3.59806 18.2133 4.01786 18.0937 4.55318L17.4482 7.44346C17.366 7.81149 17.6241 8.1684 17.998 8.20361L20.9342 8.48009C21.478 8.5313 21.6978 9.21054 21.2878 9.57303L19.0741 11.5302C18.7923 11.7794 18.7923 12.2206 19.0741 12.4698L21.2878 14.427C21.6978 14.7895 21.478 15.4687 20.9342 15.5199L17.998 15.7964C17.6241 15.8316 17.366 16.1885 17.4482 16.5565L18.0937 19.4468C18.2133 19.9821 17.638 20.4019 17.1681 20.1223L14.6309 18.6125C14.3078 18.4202 13.8901 18.5566 13.7412 18.9028L12.5721 21.6222C12.3555 22.1259 11.6445 22.1259 11.4279 21.6222L10.2588 18.9028C10.1099 18.5566 9.69222 18.4202 9.36914 18.6125L6.83191 20.1223C6.36198 20.4019 5.78673 19.9821 5.9063 19.4468L6.55183 16.5565C6.63403 16.1885 6.37587 15.8316 6.00199 15.7964L3.06579 15.5199C2.52197 15.4687 2.30224 14.7895 2.71224 14.427L4.92587 12.4698C5.20775 12.2206 5.20774 11.7794 4.92587 11.5302L2.71224 9.57303C2.30224 9.21054 2.52197 8.5313 3.0658 8.48009L6.00199 8.20361C6.37587 8.1684 6.63403 7.81149 6.55183 7.44346L5.9063 4.55318C5.78673 4.01786 6.36198 3.59806 6.83191 3.8777L9.36914 5.38751C9.69222 5.57976 10.1099 5.44343 10.2588 5.09716L11.4279 2.37775ZM17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 9.23858 9.23858 7 12 7C14.7614 7 17 9.23858 17 12Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.4279 2.37775C11.6445 1.87408 12.3555 1.87408 12.5721 2.37776L13.7412 5.09716C13.8901 5.44343 14.3078 5.57976 14.6309 5.38751L17.1681 3.8777C17.638 3.59806 18.2133 4.01786 18.0937 4.55318L17.4482 7.44346C17.366 7.81149 17.6241 8.1684 17.998 8.20361L20.9342 8.48009C21.478 8.5313 21.6978 9.21054 21.2878 9.57303L19.0741 11.5302C18.7923 11.7794 18.7923 12.2206 19.0741 12.4698L21.2878 14.427C21.6978 14.7895 21.478 15.4687 20.9342 15.5199L17.998 15.7964C17.6241 15.8316 17.366 16.1885 17.4482 16.5565L18.0937 19.4468C18.2133 19.9821 17.638 20.4019 17.1681 20.1223L14.6309 18.6125C14.3078 18.4202 13.8901 18.5566 13.7412 18.9028L12.5721 21.6222C12.3555 22.1259 11.6445 22.1259 11.4279 21.6222L10.2588 18.9028C10.1099 18.5566 9.69222 18.4202 9.36914 18.6125L6.83191 20.1223C6.36198 20.4019 5.78673 19.9821 5.9063 19.4468L6.55183 16.5565C6.63403 16.1885 6.37587 15.8316 6.00199 15.7964L3.06579 15.5199C2.52197 15.4687 2.30224 14.7895 2.71224 14.427L4.92587 12.4698C5.20775 12.2206 5.20774 11.7794 4.92587 11.5302L2.71224 9.57303C2.30224 9.21054 2.52197 8.5313 3.0658 8.48009L6.00199 8.20361C6.37587 8.1684 6.63403 7.81149 6.55183 7.44346L5.9063 4.55318C5.78673 4.01786 6.36198 3.59806 6.83191 3.8777L9.36914 5.38751C9.69222 5.57976 10.1099 5.44343 10.2588 5.09716L11.4279 2.37775ZM17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 9.23858 9.23858 7 12 7C14.7614 7 17 9.23858 17 12Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};$r.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Yi([s({type:Boolean})],$r.prototype,"useCssColor",2);$r=Yi([h("obi-palette-day-bright")],$r);var rl=Object.defineProperty,ol=Object.getOwnPropertyDescriptor,Ji=(t,e,i,o)=>{for(var r=o>1?void 0:o?ol(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&rl(e,i,r),r},Vr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7 15H11V17H7C4.24 17 2 14.76 2 12C2 9.24 4.24 7 7 7H11V9H7C5.35 9 4 10.35 4 12C4 13.65 5.35 15 7 15Z" fill="currentColor"/>
<path d="M13 7H17C19.76 7 22 9.24 22 12C22 14.76 19.76 17 17 17H13V15H17C18.65 15 20 13.65 20 12C20 10.35 18.65 9 17 9H13V7Z" fill="currentColor"/>
<path d="M16 11H8V13H16V11Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7 15H11V17H7C4.24 17 2 14.76 2 12C2 9.24 4.24 7 7 7H11V9H7C5.35 9 4 10.35 4 12C4 13.65 5.35 15 7 15Z" style="fill: var(--element-active-color)"/>
<path d="M13 7H17C19.76 7 22 9.24 22 12C22 14.76 19.76 17 17 17H13V15H17C18.65 15 20 13.65 20 12C20 10.35 18.65 9 17 9H13V7Z" style="fill: var(--element-active-color)"/>
<path d="M16 11H8V13H16V11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Vr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ji([s({type:Boolean})],Vr.prototype,"useCssColor",2);Vr=Ji([h("obi-link")],Vr);var il=Object.defineProperty,al=Object.getOwnPropertyDescriptor,Qi=(t,e,i,o)=>{for(var r=o>1?void 0:o?al(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&il(e,i,r),r},_r=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13.9999 18L15.4099 16.59L10.8299 12L15.4099 7.41L13.9999 6L7.99991 12L13.9999 18Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13.9999 18L15.4099 16.59L10.8299 12L15.4099 7.41L13.9999 6L7.99991 12L13.9999 18Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};_r.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Qi([s({type:Boolean})],_r.prototype,"useCssColor",2);_r=Qi([h("obi-chevron-left-google")],_r);var nl=Object.defineProperty,sl=Object.getOwnPropertyDescriptor,Ki=(t,e,i,o)=>{for(var r=o>1?void 0:o?sl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&nl(e,i,r),r},Zr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M20 3H4C2.9 3 2 3.9 2 5V15C2 16.1 2.9 17 4 17H10V19H8V21H16V19H14V17H20C21.1 17 22 16.1 22 15V5C22 3.9 21.1 3 20 3ZM4 15H20V5H4V15Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M20 3H4C2.9 3 2 3.9 2 5V15C2 16.1 2.9 17 4 17H10V19H8V21H16V19H14V17H20C21.1 17 22 16.1 22 15V5C22 3.9 21.1 3 20 3ZM4 15H20V5H4V15Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Zr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ki([s({type:Boolean})],Zr.prototype,"useCssColor",2);Zr=Ki([h("obi-screen-desk")],Zr);var Sr="lit-localize-status";var ea=t=>typeof t!="string"&&"strTag"in t,Ho=(t,e,i)=>{let o=t[0];for(let r=1;r<t.length;r++)o+=e[i?i[r-1]:r-1],o+=t[r];return o};var Ar=(t=>ea(t)?Ho(t.strings,t.values):t);var ae=Ar;var $o=class{constructor(e){this.__litLocalizeEventHandler=i=>{i.detail.status==="ready"&&this.host.requestUpdate()},this.host=e}hostConnected(){window.addEventListener(Sr,this.__litLocalizeEventHandler)}hostDisconnected(){window.removeEventListener(Sr,this.__litLocalizeEventHandler)}},ll=t=>t.addController(new $o(t)),ta=ll;var ra=()=>(t,e)=>(t.addInitializer(ta),t);var Pr=class{constructor(){this.settled=!1,this.promise=new Promise((e,i)=>{this._resolve=e,this._reject=i})}resolve(e){this.settled=!0,this._resolve(e)}reject(e){this.settled=!0,this._reject(e)}};var cl=[];for(let t=0;t<256;t++)cl[t]=(t>>4&15).toString(16)+(t&15).toString(16);var pl=new Pr;pl.resolve();var oa=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }
.wrapper {
  display: flex;
  user-select: none;
  padding: 8px;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  flex: 1 0 0;
}
.wrapper.style-fullwidth {
    width: 100%;
  }
.wrapper.style-compact {
    width: fit-content;
  }
.wrapper .content-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    align-self: stretch;
    align-items: center;
    gap: var(--menu-navigation-components-page-indicator-indicator-spacing);
  }
.wrapper .dot {
    width: var(--menu-navigation-components-page-indicator-indicator-size);
    height: var(--menu-navigation-components-page-indicator-indicator-size);
    border-radius: 50%;
  }
.wrapper .dot.state-inactive {
    fill: var(--indent-enabled-background-color);
    background-color: var(--indent-enabled-background-color);
  }
.wrapper .dot.state-active {
    background-color: var(--instrument-enhanced-secondary-color);
    fill: var(--instrument-enhanced-secondary-color);
  }
`;var hl=Object.defineProperty,ul=Object.getOwnPropertyDescriptor,Or=(t,e,i,o)=>{for(var r=o>1?void 0:o?ul(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&hl(e,i,r),r},dt=class extends d{constructor(){super(...arguments),this.totalSteps=5,this.currentStep=1,this.fullwidth=!1}get validCurrentStep(){return Math.max(1,Math.min(this.currentStep,this.totalSteps))}get validTotalSteps(){return Math.max(1,this.totalSteps)}renderDots(){let t=[];for(let e=0;e<this.validTotalSteps;e++)t.push(c`
        <div
          class=${V({dot:!0,"state-active":e===this.validCurrentStep-1,"state-inactive":e!==this.validCurrentStep-1})}
        ></div>
      `);return t}render(){return c`
      <div
        class=${V({wrapper:!0,"style-fullwidth":this.fullwidth,"style-compact":!this.fullwidth})}
      >
        <div class="content-container">${this.renderDots()}</div>
      </div>
    `}};dt.styles=x(oa);Or([s({type:Number})],dt.prototype,"totalSteps",2);Or([s({type:Number})],dt.prototype,"currentStep",2);Or([s({type:Boolean})],dt.prototype,"fullwidth",2);dt=Or([h("obc-progress-indicator-dots")],dt);var ia=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  display: flex;
  align-items: center;
  width: 100%;
  height: var(--menu-navigation-components-navigation-item-touch-target-size);
  transition: height 200ms;
  text-decoration: none;
  user-select: none;
}

.wrapper:focus-visible {
    outline-offset: -2px;
  }

.wrapper {
            cursor: pointer;
}

.wrapper:focus {
            outline: none;
}

.wrapper .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper:disabled {
            cursor: not-allowed;
}

.wrapper.disabled {
            cursor: not-allowed;
}

.wrapper {
  color: var(--on-flat-active-color);
}

.wrapper .visible-wrapper {
    display: flex;
    align-items: center;
    width: 100%;
    height: 100%;
    border-radius: var(
      --menu-navigation-components-navigation-item-border-radius
    );
    padding: 0px
      calc(
        var(
            --menu-navigation-components-navigation-item-margin-horizontal-list-item
          ) +
          var(--menu-navigation-components-navigation-item-padding-horizontal)
      );
  }

.wrapper {

  font-family: var(--font-family-main);

  font-weight: var(--global-typography-ui-body-font-weight);

  font-size: var(--global-typography-ui-body-font-size);

  line-height: var(--global-typography-ui-body-line-height);

  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.full .flyout-wrapper {
    display: flex;
    width: var(
      --menu-navigation-components-navigation-item-flyout-icon-container-size
    );
    align-items: center;
  }

:is(.wrapper.full .flyout-wrapper) .icon {
      flex-shrink: 0;
    }

.wrapper.icon-only,.wrapper.icon-only-large {
    width: var(--menu-navigation-components-navigation-item-touch-target-size);
    padding: var(
        --menu-navigation-components-navigation-item-margin-vertical-icon-button
      )
      var(
        --menu-navigation-components-navigation-item-margin-horizontal-icon-button
      );
  }

:is(.wrapper.icon-only,.wrapper.icon-only-large) .visible-wrapper {
      position: relative;
      padding: 0;
      display: flex;
      align-items: center;
      justify-content: center;
    }

.wrapper.icon-only-large {
    width: var(--menu-navigation-components-navigation-item-touch-target-size);
    height: var(--menu-navigation-components-navigation-item-touch-target-size);
    padding: 0;
  }

.wrapper.icon-only-large .icon.leading {
      anchor-name: --leading-icon;
    }

.wrapper.icon-only-large .icon.trailing {
      width: var(--menu-navigation-components-navigation-item-icon-size);
      height: var(--menu-navigation-components-navigation-item-icon-size);
      flex-shrink: 0;
      position: absolute;
      right: anchor(right);
      transform: translateX(60%);
      position-anchor: --leading-icon;
      top: anchor(top);
      bottom: anchor(bottom);
      margin: auto;
    }

.wrapper.compact {
    position: relative;
    width: var(
      --menu-navigation-components-navigation-item-touch-target-size-large
    );
    height: var(
      --menu-navigation-components-navigation-item-touch-target-size-large
    );
    padding: var(
        --menu-navigation-components-navigation-item-margin-vertical-icon-button
      )
      var(
        --menu-navigation-components-navigation-item-margin-horizontal-icon-button
      );
  }

.wrapper.compact .visible-wrapper {
      padding: 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }

.wrapper.compact .icon.leading {
      anchor-name: --leading-icon;
    }

.wrapper.compact .icon.trailing {
      width: var(--menu-navigation-components-navigation-item-icon-size);
      height: var(--menu-navigation-components-navigation-item-icon-size);
      flex-shrink: 0;
      position: absolute;
      right: anchor(right);
      transform: translateX(60%);
      position-anchor: --leading-icon;
      top: anchor(top);
      bottom: anchor(bottom);
      margin: auto;
    }

.wrapper.compact .label {
      font-family: var(--font-family-main);
      font-weight: var(--font-weight-regular);
      font-size: var(--global-typography-ui-label-font-size);
      line-height: var(--global-typography-ui-label-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      flex-grow: 0;
      flex-basis: auto;
    }

.checked :is(.wrapper.compact .label) {
        font-family: var(--font-family-main);
        font-weight: var(--global-typography-ui-label-active-font-weight);
        font-size: var(--global-typography-ui-label-active-font-size);
        line-height: var(--global-typography-ui-label-active-line-height);
        font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      }

.wrapper.checked {
            cursor: pointer;
}

.wrapper.checked:focus {
            outline: none;
}

.wrapper.checked .visible-wrapper {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

.wrapper.checked.activated .visible-wrapper {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

.wrapper.checked:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.checked:active .visible-wrapper {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

.wrapper.checked:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.checked:disabled .visible-wrapper {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.wrapper.checked.disabled .visible-wrapper {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.wrapper.checked:disabled {
            cursor: not-allowed;
}

.wrapper.checked.disabled {
            cursor: not-allowed;
}

.wrapper.checked {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.checked .icon.leading {
      color: var(--instrument-enhanced-secondary-color);
    }

.wrapper.group-selected .visible-wrapper {
    background: var(--flat-pressed-background-color);
    border-color: var(--flat-hover-border-color);
  }

.wrapper .icon {
    display: flex;
    align-items: center;
    color: var(--on-flat-neutral-color);
  }

.wrapper.full.has-icon .icon.leading {
    margin-right: var(
      --menu-navigation-components-navigation-item-label-spacing
    );
  }

.wrapper ::slotted([slot="icon"]),.wrapper ::slotted([slot="trailing-icon"]) {
    display: block;
    width: var(--menu-navigation-components-navigation-item-icon-size);
    height: var(--menu-navigation-components-navigation-item-icon-size);
  }

.wrapper .icon.trailing {
    width: var(--menu-navigation-components-navigation-item-icon-size);
    height: var(--menu-navigation-components-navigation-item-icon-size);
  }

.wrapper .label {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
  }
`;var vl=Object.defineProperty,ml=Object.getOwnPropertyDescriptor,aa=(t,e,i,o)=>{for(var r=o>1?void 0:o?ml(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&vl(e,i,r),r},Br=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M9.5 15.0687C9.5 15.6745 9.5 15.9774 9.6198 16.1177C9.72374 16.2394 9.87967 16.304 10.0392 16.2914C10.2231 16.2769 10.4373 16.0627 10.8657 15.6344L13.9343 12.5657C14.1323 12.3677 14.2313 12.2687 14.2684 12.1546C14.3011 12.0541 14.3011 11.946 14.2684 11.8455C14.2313 11.7314 14.1323 11.6324 13.9343 11.4344L10.8657 8.36573C10.4373 7.93736 10.2231 7.72317 10.0392 7.7087C9.87967 7.69614 9.72374 7.76073 9.6198 7.88243C9.5 8.0227 9.5 8.3256 9.5 8.93142L9.5 15.0687Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M9.5 15.0687C9.5 15.6745 9.5 15.9774 9.6198 16.1177C9.72374 16.2394 9.87967 16.304 10.0392 16.2914C10.2231 16.2769 10.4373 16.0627 10.8657 15.6344L13.9343 12.5657C14.1323 12.3677 14.2313 12.2687 14.2684 12.1546C14.3011 12.0541 14.3011 11.946 14.2684 11.8455C14.2313 11.7314 14.1323 11.6324 13.9343 11.4344L10.8657 8.36573C10.4373 7.93736 10.2231 7.72317 10.0392 7.7087C9.87967 7.69614 9.72374 7.76073 9.6198 7.88243C9.5 8.0227 9.5 8.3256 9.5 8.93142L9.5 15.0687Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Br.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;aa([s({type:Boolean})],Br.prototype,"useCssColor",2);Br=aa([h("obi-arrow-flyout-google")],Br);var na=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.wrapper {
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  width: 320px;
  background: var(--container-global-color, #fcfcfc);
  box-shadow: var(--shadow-flat);
}

.wrapper nav {
    padding: var(--app-components-navigation-menu-margin-vertical)
      var(--app-components-navigation-menu-footer-margin-horizontal);
  }

.wrapper.icon-only,.wrapper.compact {
    width: fit-content;
  }

:is(.wrapper.icon-only,.wrapper.compact) nav.main {
      padding: var(--app-components-navigation-menu-margin-vertical) 0px;
    }

:is(.wrapper.icon-only,.wrapper.compact) .footer nav {
      padding: 0;
    }

.wrapper.icon-only-large {
    width: fit-content;
  }

.wrapper .main {
    flex: 1;
  }

.wrapper .footer {
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--border-outline-color);
    flex: 0;
  }

.wrapper.small-screen .footer nav ol {
    display: flex;
    justify-content: space-around;
    width: 100%;
  }

.full .footer.has-footer nav {
  border-bottom: 1px solid var(--border-outline-color);
}

.full .logo {
  height: 96px;
  width: 100%;
}

.icon-only-large .footer nav {
  padding-bottom: 0;
}

.icon-only-large .logo {
  padding: var(--app-components-navigation-menu-margin-vertical)
    var(--app-components-navigation-menu-footer-margin-horizontal);
  padding-top: 0;
  height: calc(
    var(--menu-navigation-components-navigation-item-touch-target-size) +
      var(--app-components-navigation-menu-margin-vertical)
  );
}

.icon-only .logo {
  height: var(--menu-navigation-components-navigation-item-touch-target-size);
}

.compact .logo {
  height: var(
    --menu-navigation-components-navigation-item-touch-target-size-large
  );
}

.logo {
  transition: height 200ms;
}

.wrapper:not(.small-screen) ::slotted([slot="logo"]) {
  width: 100%;
}

ol {
  list-style: none;
  margin: 0;
  padding: 0;
}
`;var fl=Object.defineProperty,gl=Object.getOwnPropertyDescriptor,_t=(t,e,i,o)=>{for(var r=o>1?void 0:o?gl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&fl(e,i,r),r},Ke=(t=>(t.Full="full",t.IconOnly="icon-only",t.IconOnlyLarge="icon-only-large",t.Compact="compact",t))(Ke||{});var Qe=class extends d{constructor(){super(...arguments),this.variant="full",this.flyoutVariant="full",this.smallScreen=!1,this.slotObservers=[],this.hasFooter=!1}findAllElements(t,e,{slot:i,stopTag:o}={}){let r=[];for(let a of t.children)if(a.tagName.toLowerCase()===e){if(i&&a.getAttribute("slot")!==i)continue;r.push(a)}else{if(o&&a.tagName.toLowerCase()===o)continue;if(i&&a.getAttribute("slot")!==i)continue;r.push(...this.findAllElements(a,e,{stopTag:o}))}return r}findAllGroups(t){return this.findAllElements(t,"obc-navigation-item-group")}findRootItems(t){return this.findAllElements(t,"obc-navigation-item",{stopTag:"obc-navigation-item-group"})}findAllItems(t,e){return this.findAllElements(t,"obc-navigation-item",{slot:e})}closeAllGroups(){this.findAllGroups(this).forEach(e=>{e.close()})}registerGroup(t){t.forEach(e=>{e.addEventListener("open",()=>{t.forEach(o=>{o!==e&&o.close()})});let i=this.findAllGroups(e);this.registerGroup(i)})}cleanupSlotObservers(){this.slotObservers.forEach(t=>t.disconnect()),this.slotObservers=[]}setupSlotObservers(){this.cleanupSlotObservers();let t=this.shadowRoot?.querySelector('slot[name="main"]'),e=this.shadowRoot?.querySelector('slot[name="footer"]');this.hasFooter=e?.assignedElements().length>0,[t,e].forEach(i=>{i&&i.assignedElements().forEach(r=>{let a=new MutationObserver(()=>{this.setupItems()});a.observe(r,{childList:!0,subtree:!0}),this.slotObservers.push(a)})})}firstUpdated(t){super.firstUpdated(t);let e=this.findAllGroups(this);this.registerGroup(e)}updated(t){super.updated(t),(t.has("variant")||t.has("flyoutVariant"))&&this.setupItems()}setVariantToFlyoutItems(t){this.findAllElements(t,"obc-navigation-item").forEach(o=>{o.variant="full"}),this.findAllGroups(t).forEach(o=>{o.variant="full",this.setVariantToFlyoutItems(o)})}disconnectedCallback(){super.disconnectedCallback(),this.cleanupSlotObservers()}handleSlotChange(){this.setupItems(),this.setupSlotObservers()}setupItems(){let t=this.variant!=="full"||this.flyoutVariant==="compact";this.setHugToGroups(this,t),this.findAllGroups(this).forEach(o=>{o.variant=this.variant,this.setVariantToFlyoutItems(o)}),this.findRootItems(this).forEach(o=>{o.variant=this.variant});let i=this.smallScreen&&this.variant==="full"?"compact":this.variant;this.findAllItems(this,"footer").forEach(o=>{o.variant=i}),this.findAllItems(this,"logo").forEach(o=>{o.variant=i}),this.findAllItems(this).forEach(o=>{o.addEventListener("click",()=>{this.closeAllGroups()})})}setHugToGroups(t,e){this.findAllGroups(t).forEach(o=>{o.hug=e,this.setHugToGroups(o,e)})}render(){return c`
      <div
        class="wrapper ${this.variant} ${this.smallScreen?"small-screen":""}"
      >
        <nav class="main">
          <ol>
            <slot name="main" @slotchange=${this.handleSlotChange}></slot>
          </ol>
        </nav>
        <div class="footer ${this.hasFooter?"has-footer":""}">
          <nav>
            <ol>
              <slot name="footer" @slotchange=${this.handleSlotChange}></slot>
              ${this.smallScreen?c` <slot name="logo"></slot> `:f}
            </ol>
          </nav>
          ${this.smallScreen?f:c`
                <div class="logo">
                  <slot name="logo"></slot>
                </div>
              `}
        </div>
      </div>
    `}};Qe.styles=x(na);_t([s({type:String})],Qe.prototype,"variant",2);_t([s({type:String})],Qe.prototype,"flyoutVariant",2);_t([s({type:Boolean})],Qe.prototype,"smallScreen",2);_t([re()],Qe.prototype,"hasFooter",2);Qe=_t([h("obc-navigation-menu")],Qe);var bl=Object.defineProperty,Cl=Object.getOwnPropertyDescriptor,Te=(t,e,i,o)=>{for(var r=o>1?void 0:o?Cl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&bl(e,i,r),r},ye=class extends d{constructor(){super(...arguments),this.label="Label",this.checked=!1,this.variant=Ke.Full,this.group=!1,this.groupSelected=!1,this.hasIcon=!1,this.hasTrailingIcon=!1}onClick(){dispatchEvent(new CustomEvent("click"))}render(){let t=this.group&&this.variant!==Ke.IconOnly,e=this.variant===Ke.Compact;return c`
      <a
        class="${V({wrapper:!0,checked:this.checked,"group-selected":this.groupSelected&&this.group,"has-icon":this.hasIcon,[this.variant]:!0})}"
        href=${oe(this.href)}
        @click=${this.onClick}
      >
        <div class="visible-wrapper">
          ${this.hasIcon?c`<slot name="icon" class="icon leading"></slot>`:f}
          ${[Ke.IconOnly,Ke.IconOnlyLarge].includes(this.variant)?f:c`
                <span
                  part="label"
                  class=${V({label:!0,"label-flyout":t&&!e})}
                >
                  ${this.label}
                </span>
              `}
          ${t?c`
                <div class="flyout-wrapper">
                  <obi-arrow-flyout-google
                    class="icon trailing"
                  ></obi-arrow-flyout-google>
                </div>
              `:f}
          ${this.hasTrailingIcon&&!t?c`<slot name="trailing-icon" class="icon trailing"></slot>`:f}
        </div>
      </a>
    `}};ye.styles=x(ia);Te([s({type:String})],ye.prototype,"label",2);Te([s({type:String})],ye.prototype,"href",2);Te([s({type:Boolean})],ye.prototype,"checked",2);Te([s({type:String})],ye.prototype,"variant",2);Te([s({type:Boolean})],ye.prototype,"group",2);Te([s({type:Boolean})],ye.prototype,"groupSelected",2);Te([s({type:Boolean,reflect:!0})],ye.prototype,"hasIcon",2);Te([s({type:Boolean})],ye.prototype,"hasTrailingIcon",2);ye=Te([h("obc-navigation-item")],ye);var sa=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  display: inline-flex;
  min-width: var(--ui-components-app-button-touch-target-size-enhanced);
  min-height: var(--ui-components-app-button-touch-target-size-enhanced);
  padding: var(--ui-components-app-button-padding-vertical-enhanced) 0px;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  border-radius: var(--ui-components-app-button-border-radius-container);
  border-width: 0 !important;
}

.wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper:focus {
            outline: none;
}

.wrapper.activated {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper:hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper:focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

:is(.wrapper .icon-wrapper) {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper .icon-wrapper {
    color: var(--on-normal-neutral-color);

    width: var(--ui-components-app-button-visual-size-enhanced);
    height: var(--ui-components-app-button-visual-size-enhanced);
    border-radius: var(--ui-components-app-button-border-radius-large);

    display: flex;

    align-items: center;
    justify-content: center;
  }

:is(.wrapper .icon-wrapper) .icon {
      width: var(--ui-components-app-button-icon-size-enhanced);
      height: var(--ui-components-app-button-icon-size-enhanced);
    }

.wrapper .label {
    color: var(--element-active-color);
    text-align: center;
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.wrapper.small {
    min-width: var(--ui-components-app-button-touch-target-size);
    min-height: var(--ui-components-app-button-touch-target-size);
    padding: var(--ui-components-app-button-padding-vertical) 0px;
  }

.wrapper.small .icon-wrapper {
      width: var(--ui-components-app-button-visual-size);
      height: var(--ui-components-app-button-visual-size);
      border-radius: var(--ui-components-app-button-border-radius-small);
    }

.wrapper.small .icon {
      width: var(--ui-components-app-button-icon-size);
      height: var(--ui-components-app-button-icon-size);
    }

:is(.wrapper.checked .icon-wrapper) {
            border-color: var(--selected-enabled-border-color);
            background-color: var(--selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--selected-enabled-border-color);
            --base-background-color: var(--selected-enabled-background-color);
}

:is(.wrapper.checked .icon-wrapper):focus {
            outline: none;
}

.activated:is(.wrapper.checked .icon-wrapper) {
            border-color: var(--selected-activated-border-color);
            background-color: var(--selected-activated-background-color);
            --base-border-color: var(--selected-activated-border-color);
            --base-background-color: var(--selected-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.checked .icon-wrapper):hover {
                        border-color: color-mix(in srgb, var(--selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.checked .icon-wrapper):active {
            border-color: var(--selected-pressed-border-color);
            background-color: var(--selected-pressed-background-color);
}

:is(.wrapper.checked .icon-wrapper):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.checked .icon-wrapper):disabled {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.disabled:is(.wrapper.checked .icon-wrapper) {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.wrapper.checked .icon-wrapper {
      color: var(--on-selected-active-color);
    }

.wrapper.checked .label {
      font-family: var(--font-family-main);
      font-weight: var(--global-typography-ui-label-active-font-weight);
      font-size: var(--global-typography-ui-label-active-font-size);
      line-height: var(--global-typography-ui-label-active-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    }

:is(.wrapper.integration .icon-wrapper) {
            border-color: var(--integration-normal-enabled-border-color);
            background-color: var(--integration-normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--integration-normal-enabled-border-color);
            --base-background-color: var(--integration-normal-enabled-background-color);
}

.wrapper.integration .icon-wrapper {
      color: var(--integration-on-normal-neutral-color);
    }

.wrapper.integration .label {
      font-family: var(--font-family-main);
      font-weight: var(--font-weight-regular);
      font-size: var(--global-typography-ui-label-font-size);
      line-height: var(--global-typography-ui-label-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      color: var(--integration-on-normal-neutral-color);
    }

:is(.wrapper.integration.checked .icon-wrapper) {
            border-color: var(--integration-selected-enabled-border-color);
            background-color: var(--integration-selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--integration-selected-enabled-border-color);
            --base-background-color: var(--integration-selected-enabled-background-color);
}

:is(.wrapper.integration.checked .icon-wrapper):focus {
            outline: none;
}

.activated:is(.wrapper.integration.checked .icon-wrapper) {
            border-color: var(--integration-selected-activated-border-color);
            background-color: var(--integration-selected-activated-background-color);
            --base-border-color: var(--integration-selected-activated-border-color);
            --base-background-color: var(--integration-selected-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.integration.checked .icon-wrapper):hover {
                        border-color: color-mix(in srgb, var(--integration-selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--integration-selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.integration.checked .icon-wrapper):active {
            border-color: var(--integration-selected-pressed-border-color);
            background-color: var(--integration-selected-pressed-background-color);
}

:is(.wrapper.integration.checked .icon-wrapper):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.integration.checked .icon-wrapper):disabled {
            border-color: var(--integration-selected-disabled-border-color);
            background-color: var(--integration-selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-selected-disabled-color) !important;
}

.disabled:is(.wrapper.integration.checked .icon-wrapper) {
            border-color: var(--integration-selected-disabled-border-color);
            background-color: var(--integration-selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-selected-disabled-color) !important;
}

.wrapper.integration.checked .icon-wrapper {
      color: var(--integration-on-selected-active-color);
    }

.wrapper.integration.checked .label {
      font-family: var(--font-family-main);
      font-weight: var(--global-typography-ui-label-active-font-weight);
      font-size: var(--global-typography-ui-label-active-font-size);
      line-height: var(--global-typography-ui-label-active-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      color: var(--integration-element-active-color);
    }

.wrapper.disabled {
    cursor: not-allowed;
  }

.wrapper.disabled .icon-wrapper {
      color: var(--element-disabled-color);
    }

.wrapper.disabled .label {
      color: var(--element-disabled-color);
    }

.wrapper.checked.disabled .icon-wrapper {
    background-color: var(--selected-disabled-background-color);
    border-color: var(--selected-disabled-border-color);
    color: var(--on-selected-disabled-color);
  }

.wrapper.integration.disabled .icon-wrapper {
      color: var(--element-disabled-color);
    }

.wrapper.integration.disabled .label {
      color: var(--element-disabled-color);
    }
`;var yl=Object.defineProperty,wl=Object.getOwnPropertyDescriptor,et=(t,e,i,o)=>{for(var r=o>1?void 0:o?wl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&yl(e,i,r),r};var Ee=class extends d{constructor(){super(...arguments),this.label="Button",this.checked=!1,this.showLabel=!0,this.integration=!1,this.size="normal",this.disabled=!1}render(){return c` <button
      class="${V({wrapper:!0,checked:this.checked,small:this.size==="small",integration:this.integration,disabled:this.disabled})}"
      ?disabled=${this.disabled}
    >
      <div class="icon-wrapper">
        <span class="icon">
          <slot name="icon"></slot>
        </span>
      </div>
      ${this.showLabel?c`<div class="label">${this.label}</div>`:f}
    </button>`}};Ee.styles=x(sa);et([s({type:String})],Ee.prototype,"label",2);et([s({type:Boolean})],Ee.prototype,"checked",2);et([s({type:Boolean,attribute:!1})],Ee.prototype,"showLabel",2);et([s({type:Boolean})],Ee.prototype,"integration",2);et([s({type:String})],Ee.prototype,"size",2);et([s({type:Boolean})],Ee.prototype,"disabled",2);Ee=et([h("obc-app-button")],Ee);var la=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

.wrapper {
  display: flex;
  user-select: none;
  min-width: var(--ui-components-user-button-touch-target-size);
  min-height: var(--ui-components-app-button-touch-target-size);
  width: fit-content;
  padding: var(--ui-components-user-button-padding-vertical) 0px;
  margin: 0;
  appearance: none;
  justify-content: center;
  align-items: center;
  border-radius: var(--ui-components-user-button-border-radius-container);
  border: none;
  background: transparent;
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.size-large {
    min-width: var(--ui-components-user-button-touch-target-size-enhanced);
    min-height: var(--ui-components-user-button-touch-target-size-enhanced);
    padding: var(--ui-components-user-button-padding-vertical-enhanced) 0px;
  }

.wrapper.size-large .user-button-circle {
      width: var(--ui-components-user-button-visual-size-enhanced);
      height: var(--ui-components-user-button-visual-size-enhanced);
    }

.wrapper.size-large .icon-container {
      width: var(--ui-components-user-button-icon-size-enhanced);
      height: var(--ui-components-user-button-icon-size-enhanced);
    }

.wrapper.size-large .user-initials {
      font-family: var(--font-family-main);
      font-weight: var(--font-weight-regular);
      font-size: var(--font-size-150);
      line-height: var(--line-height-150);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    }

.wrapper.size-large.style-selected .user-initials {
      font-family: var(--font-family-main);
      font-weight: var(--font-weight-bold);
      font-size: var(--font-size-150);
      line-height: var(--line-height-150);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    }

.wrapper.size-large.state-static {
      width: var(--ui-components-user-button-visual-size-enhanced);
      height: var(--ui-components-user-button-visual-size-enhanced);
      min-width: unset;
      min-height: unset;
      padding: 0;
      margin: 0;
    }

.wrapper .user-label {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-regular);
    font-size: var(--global-typography-ui-label-font-size);
    line-height: var(--global-typography-ui-label-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--element-active-color);
  }

.wrapper:disabled .user-label {
    color: var(--element-disabled-color);
  }

.wrapper .user-button-circle {
    display: flex;
    width: var(--ui-components-user-button-visual-size);
    height: var(--ui-components-user-button-visual-size);
    flex-direction: column;
    justify-content: center;
    align-items: center;
    border-radius: 100px;
  }

.wrapper.state-static {
    width: var(--ui-components-user-button-visual-size);
    height: var(--ui-components-user-button-visual-size);
    min-width: unset;
    min-height: unset;
    padding: 0;
    margin: 0;
  }

.wrapper.style-flat {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.style-flat:not(.state-static) {
            cursor: pointer;
}

.wrapper.style-flat:not(.state-static):focus {
            outline: none;
}

.wrapper.style-flat:not(.state-static) .user-button-circle {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.style-flat.activated:not(.state-static) .user-button-circle {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.style-flat:not(.state-static):hover .user-button-circle {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.style-flat:not(.state-static):active .user-button-circle {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.style-flat:not(.state-static):focus-visible .user-button-circle {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.style-flat:not(.state-static):disabled .user-button-circle {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-flat.disabled:not(.state-static) .user-button-circle {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-flat:not(.state-static):disabled {
            cursor: not-allowed;
}

.wrapper.style-flat.disabled:not(.state-static) {
            cursor: not-allowed;
}

.wrapper.style-flat .user-icon {
    color: var(--on-flat-neutral-color);
  }

.wrapper.style-flat .user-button-circle {
    border-radius: var(--ui-components-button-border-radius-top-left)
      var(--ui-components-button-border-radius-top-right)
      var(--ui-components-button-border-radius-bottom-right)
      var(--ui-components-button-border-radius-bottom-left);
    color: var(--on-flat-neutral-color);
  }

.wrapper.style-normal:not(.state-static) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.style-normal:not(.state-static):focus {
            outline: none;
}

.wrapper.style-normal.activated:not(.state-static) {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.style-normal:not(.state-static):hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.style-normal:not(.state-static):active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.style-normal:not(.state-static):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.style-normal:not(.state-static):disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-normal.disabled:not(.state-static) {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-normal .user-button-circle {
    border: 1px solid var(--normal-enabled-border-color);
    background: var(--normal-enabled-background-color);
    color: var(--on-normal-neutral-color);
  }

.wrapper.style-normal.mode-initials .user-button-circle {
    color: var(--element-neutral-color);
  }

.wrapper.style-normal.mode-initials:disabled .user-button-circle {
    color: var(--element-disabled-color);
    background-color: var(--normal-disabled-background-color);
    border-color: var(--normal-disabled-border-color);
  }

.wrapper.style-normal.mode-icon:disabled .user-button-circle {
    color: var(--on-normal-disabled-color);
    background-color: var(--normal-disabled-background-color);
    border-color: var(--normal-disabled-border-color);
  }

.wrapper.style-selected {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.style-selected:not(.state-static) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.style-selected:not(.state-static):focus {
            outline: none;
}

.wrapper.style-selected.activated:not(.state-static) {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.style-selected:not(.state-static):hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.style-selected:not(.state-static):active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.style-selected:not(.state-static):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.style-selected:not(.state-static):disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-selected.disabled:not(.state-static) {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.style-selected .user-button-circle {
    color: var(--on-selected-active-color);
    border: 1px solid var(--selected-enabled-border-color);
    background: var(--selected-enabled-background-color);
  }

.wrapper.style-selected .user-label {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-label-active-font-weight);
    font-size: var(--global-typography-ui-label-active-font-size);
    line-height: var(--global-typography-ui-label-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.wrapper.style-selected:disabled .user-button-circle {
    color: var(--on-selected-disabled-color);
    background-color: var(--selected-disabled-background-color);
    border-color: var(--selected-disabled-border-color);
  }

.content-container {
  display: flex;
  justify-content: center;
  align-items: center;
  align-self: stretch;
  flex-direction: column;
}

.icon-container {
  width: var(--ui-components-user-button-icon-size);
  height: var(--ui-components-user-button-icon-size);
  flex-shrink: 0;
}

.chip-icon-wrapper ::slotted(*) {
  width: 100%;
  height: 100%;
  flex-shrink: 0;
}
`;var Ll=Object.defineProperty,kl=Object.getOwnPropertyDescriptor,je=(t,e,i,o)=>{for(var r=o>1?void 0:o?kl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ll(e,i,r),r};var $e=class extends d{constructor(){super(...arguments),this.variant="icon",this.size="regular",this.styleType="flat",this.static=!1,this.disabled=!1,this.initials=""}get formattedInitials(){if(!this.initials)return"";let t=this.initials.replace(/\s+/g,"").toUpperCase(),e=this.size==="large"?3:2;return t.length>e?(console.warn(`Initials "${this.initials}" are longer than ${e} characters.`),t.slice(0,e)):t}get shouldShowIcon(){return this.variant==="icon"}render(){let t=this.size==="large"&&this.styleType==="flat"?"normal":this.styleType,e={wrapper:!0,"wrapper-static":this.static,[`style-${t}`]:!0,"mode-icon":this.shouldShowIcon,"mode-initials":!this.shouldShowIcon,"state-static":this.static,[`size-${this.size}`]:!0},i=this.static?R`div`:R`button`,o=this.label&&!this.static?_`<span class="user-label" part="label">${this.label}</span>`:f;return _`
        <${i}
          class=${V(e)}
          ?disabled=${this.disabled}
          aria-label=${this.initials||"User button"}
        >
        <div class="content-container" part="content-container">
          <div class="user-button-circle">
            ${this.shouldShowIcon?_`
                    <div class="icon-container">
                      <slot name="icon">
                        <!-- Fallback to default icon if no slot content -->
                        <obi-user></obi-user>
                      </slot>
                    </div>
                  `:_`
                    <span class="user-initials">
                      ${this.formattedInitials}
                    </span>
                  `}
          </div>
          ${o}
        </div>
        </${i}>
      `}};$e.styles=x(la);je([s({type:String})],$e.prototype,"variant",2);je([s({type:String})],$e.prototype,"size",2);je([s({type:String})],$e.prototype,"styleType",2);je([s({type:Boolean})],$e.prototype,"static",2);je([s({type:Boolean})],$e.prototype,"disabled",2);je([s({type:String})],$e.prototype,"initials",2);je([s({type:String})],$e.prototype,"label",2);$e=je([h("obc-user-button")],$e);var ca=p`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  display: block;
}

.tab-container {
  display: flex;
  width: 100%;
  height: 100%;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  border-radius: var(--app-components-alert-menu-border-radius);
  background: var(--container-global-color);
  box-shadow: var(--shadow-floating);
}

.tab-header {
  display: flex;
  align-items: center;
  align-self: stretch;
  border-top-left-radius: var(--app-components-alert-menu-border-radius);
  border-top-right-radius: var(--app-components-alert-menu-border-radius);
  background: var(--container-section-color);
}

.tab-button {
  position: relative;
  display: flex;
  height: var(--menu-navigation-components-tab-item-touch-target-size);
  padding: 0 var(--menu-navigation-components-tab-item-padding-horizontal);
  justify-content: center;
  align-items: center;
  flex: 1 0 0;
}

.tab-button {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.tab-button:focus {
            outline: none;
}

.tab-button.activated {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.tab-button:hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.tab-button:active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.tab-button:focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.tab-button:disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.tab-button.disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.tab-button {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-active-color);
  border-width: 0;
  border-bottom: 1px solid var(--border-divider-color);
}

.tab-button .tab-title-container {
    display: flex;
    align-items: center;
  }

:is(.tab-button .tab-title-container) .tab-icon {
      color: var(--on-flat-neutral-color);
    }

:is(.tab-button .tab-title-container) .tab-title {
      display: block;
      padding: 0 var(--menu-navigation-components-tab-item-label-spacing);
    }

/* Divider between tabs */

.tab-button.has-divider::after {
    content: "";
    position: absolute;
    top: 0;
    bottom: 0;
    margin: auto;
    right: 0;
    width: 1px;
    height: 24px;
    background: var(--border-divider-color);
    z-index: 0;
  }

.tab-button[aria-selected="true"] {
    font-family: var(--font-family-main);
    font-weight: var(--font-weight-bold);
    font-size: var(--global-typography-ui-body-active-font-size);
    line-height: var(--global-typography-ui-body-active-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.tab-button[aria-selected="true"] {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.tab-button[aria-selected="true"]:focus {
            outline: none;
}

.tab-button.activated[aria-selected="true"] {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.tab-button[aria-selected="true"]:hover {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.tab-button[aria-selected="true"]:active {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.tab-button[aria-selected="true"]:focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.tab-button[aria-selected="true"]:disabled {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.tab-button.disabled[aria-selected="true"] {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.tab-button[aria-selected="true"] {
    border-width: 0;
    border-bottom: 1px solid transparent !important;
    border-color: transparent;
    z-index: 1;
}

.tab-button[aria-selected="true"]:not(:last-of-type) {
      border-right: 1px solid var(--border-divider-color);
    }

.tab-button[aria-selected="true"]:not(:first-of-type) {
      border-left: 1px solid var(--border-divider-color);
    }

.tab-button[aria-selected="true"] .tab-icon {
      color: var(--instrument-enhanced-secondary-color);
    }

.tab-button:first-of-type {
    border-top-left-radius: var(--app-components-alert-menu-border-radius);
  }

.tab-button:last-of-type {
    border-top-right-radius: var(--app-components-alert-menu-border-radius);
  }

.tab-panels {
  width: 100%;
  flex: 1;
  min-height: 0;
}

div[role="tabpanel"] {
  width: 100%;
  height: 100%;
  border-bottom-left-radius: var(--app-components-alert-menu-border-radius);
  border-bottom-right-radius: var(--app-components-alert-menu-border-radius);
  overflow: hidden;
}
`;var Ml=Object.defineProperty,xl=Object.getOwnPropertyDescriptor,Zt=(t,e,i,o)=>{for(var r=o>1?void 0:o?xl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ml(e,i,r),r},tt=class extends d{constructor(){super(...arguments),this.nTabs=1,this.selectedTab=0,this.hasDefaultSlotOnly=!1,this.hasTabIcons=!1}_handleKeyDown(t){if(!t.target.classList.contains("tab-button"))return;let i=this.selectedTab;switch(t.key){case"ArrowRight":this.setSelectedTab((i+1)%this.nTabs);break;case"ArrowLeft":this.setSelectedTab((i-1+this.nTabs)%this.nTabs);break;case"Home":this.setSelectedTab(0);break;case"End":this.setSelectedTab(this.nTabs-1);break;default:return}t.preventDefault(),this._focusTab(this.selectedTab)}setSelectedTab(t){this.selectedTab=t,this.dispatchEvent(new CustomEvent("tab-change",{detail:{tab:t}}))}_focusTab(t){this.shadowRoot?.querySelector(`button[data-index="${t}"]`)?.focus()}_generateTabHeaders(){return[...Array(this.nTabs)].map((t,e)=>{let i=e!==this.nTabs-1&&this.selectedTab!==e&&e+1!==this.selectedTab,o=this.hasTabIcons?c`<span class="tab-icon">
            <slot name="tab-icon-${e}"></slot>
          </span>`:f;return c`
        <button
          class="tab-button ${i?"has-divider":""}"
          role="tab"
          aria-selected="${this.selectedTab===e}"
          aria-controls="panel-${e}"
          id="tab-${e}"
          data-index="${e}"
          tabindex="${this.selectedTab===e?0:-1}"
          @click="${()=>this.setSelectedTab(e)}"
          @focus="${()=>this.setSelectedTab(e)}"
        >
          <div class="tab-title-container">
            ${o}
            <slot class="tab-title" name="tab-title-${e}"
              >Tab ${e+1}</slot
            >
          </div>
        </button>
      `})}_generateTabPanels(){return this.hasDefaultSlotOnly?c`<div
        role="tabpanel"
        class="tab-content"
        id="panel-${this.selectedTab}"
        aria-labelledby="tab-${this.selectedTab}"
        tabindex="0"
      >
        <slot></slot>
      </div>`:[...Array(this.nTabs)].map((t,e)=>c`
        <div
          role="tabpanel"
          id="panel-${e}"
          aria-labelledby="tab-${e}"
          tabindex="0"
          ?hidden="${this.selectedTab!==e}"
        >
          <slot name="tab-content-${e}"></slot>
        </div>
      `)}render(){return c`
      <div class="tab-container" @keydown="${this._handleKeyDown}">
        <div class="tab-header" role="tablist" aria-label="Tab List">
          ${this._generateTabHeaders()}
        </div>
        <div class="tab-panels">${this._generateTabPanels()}</div>
      </div>
    `}};tt.styles=x(ca);Zt([s({type:Number})],tt.prototype,"nTabs",2);Zt([s({type:Number})],tt.prototype,"selectedTab",2);Zt([s({type:Boolean})],tt.prototype,"hasDefaultSlotOnly",2);Zt([s({type:Boolean})],tt.prototype,"hasTabIcons",2);tt=Zt([h("obc-tabbed-card")],tt);var Hl=Object.defineProperty,$l=Object.getOwnPropertyDescriptor,da=(t,e,i,o)=>{for(var r=o>1?void 0:o?$l(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Hl(e,i,r),r},Tr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20.5C16.6944 20.5 20.5 16.6944 20.5 12C20.5 7.30558 16.6944 3.5 12 3.5C7.30558 3.5 3.5 7.30558 3.5 12C3.5 16.6944 7.30558 20.5 12 20.5ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 13.5C12.8284 13.5 13.5 12.8284 13.5 12C13.5 11.1716 12.8284 10.5 12 10.5C11.1716 10.5 10.5 11.1716 10.5 12C10.5 12.8284 11.1716 13.5 12 13.5ZM12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" fill="currentColor"/>
<path d="M11.25 5H12.75V7.5H11.25V5Z" fill="currentColor"/>
<path d="M19 11.25V12.75H16.5V11.25H19Z" fill="currentColor"/>
<path d="M7.58008 17.48L6.51942 16.4193L8.28719 14.6516L9.34785 15.7122L7.58008 17.48Z" fill="currentColor"/>
<path d="M6.51953 7.58008L7.58019 6.51942L9.34796 8.28719L8.2873 9.34785L6.51953 7.58008Z" fill="currentColor"/>
<path d="M11.25 16.5H12.75V19H11.25V16.5Z" fill="currentColor"/>
<path d="M7.5 11.25V12.75H5V11.25H7.5Z" fill="currentColor"/>
<path d="M15.7129 9.34839L14.6522 8.28773L16.42 6.51996L17.4807 7.58062L15.7129 9.34839Z" fill="currentColor"/>
<path d="M14.6523 15.7122L15.713 14.6515L17.4808 16.4193L16.4201 17.4799L14.6523 15.7122Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20.5C16.6944 20.5 20.5 16.6944 20.5 12C20.5 7.30558 16.6944 3.5 12 3.5C7.30558 3.5 3.5 7.30558 3.5 12C3.5 16.6944 7.30558 20.5 12 20.5ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 13.5C12.8284 13.5 13.5 12.8284 13.5 12C13.5 11.1716 12.8284 10.5 12 10.5C11.1716 10.5 10.5 11.1716 10.5 12C10.5 12.8284 11.1716 13.5 12 13.5ZM12 15C13.6569 15 15 13.6569 15 12C15 10.3431 13.6569 9 12 9C10.3431 9 9 10.3431 9 12C9 13.6569 10.3431 15 12 15Z" style="fill: var(--element-active-color)"/>
<path d="M11.25 5H12.75V7.5H11.25V5Z" style="fill: var(--element-active-color)"/>
<path d="M19 11.25V12.75H16.5V11.25H19Z" style="fill: var(--element-active-color)"/>
<path d="M7.58008 17.48L6.51942 16.4193L8.28719 14.6516L9.34785 15.7122L7.58008 17.48Z" style="fill: var(--element-active-color)"/>
<path d="M6.51953 7.58008L7.58019 6.51942L9.34796 8.28719L8.2873 9.34785L6.51953 7.58008Z" style="fill: var(--element-active-color)"/>
<path d="M11.25 16.5H12.75V19H11.25V16.5Z" style="fill: var(--element-active-color)"/>
<path d="M7.5 11.25V12.75H5V11.25H7.5Z" style="fill: var(--element-active-color)"/>
<path d="M15.7129 9.34839L14.6522 8.28773L16.42 6.51996L17.4807 7.58062L15.7129 9.34839Z" style="fill: var(--element-active-color)"/>
<path d="M14.6523 15.7122L15.713 14.6515L17.4808 16.4193L16.4201 17.4799L14.6523 15.7122Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Tr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;da([s({type:Boolean})],Tr.prototype,"useCssColor",2);Tr=da([h("obi-display-brilliance-iec")],Tr);var Vl=Object.defineProperty,_l=Object.getOwnPropertyDescriptor,q=(t,e,i,o)=>{for(var r=o>1?void 0:o?_l(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Vl(e,i,r),r};var N=class extends d{constructor(){super(...arguments),this.palette="day",this.brightness=50,this.showLinkBrightness=!1,this.showLinkPalette=!1,this.showBrightness=!0,this.showPalette=!0,this.showNightPalette=!0,this.showDuskPalette=!0,this.showDayPalette=!0,this.showBrightPalette=!0,this.variant="normal",this.brightnessUnit="%",this.brightnessMax=100,this.brightnessMinorStep=5,this.brightnessMajorStep=25,this.brightnessInputVariant="buttons",this.showScreenControlLink=!1}willUpdate(t){if(this.showPalette){let e=this.availablePalettes;e.length>0&&!e.includes(this.palette)&&(this.palette=e[0],this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}})))}}onPaletteChanged(t){this.palette=t.detail.value,this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:t.detail.value}}))}handleBrightnessChanged(t){this.brightness=t.detail,this.dispatchEvent(new CustomEvent("brightness-changed",{detail:{value:t.detail}}))}increaseBrightness(t){this.brightness=Math.max(0,Math.min(this.brightness+t,this.brightnessMax)),this.dispatchEvent(new CustomEvent("brightness-changed",{detail:{value:this.brightness}}))}get canIncreaseBrightness(){return this.brightness<this.brightnessMax}get canDecreaseBrightness(){return this.brightness>0}onLinkPaletteChanged(t){this.dispatchEvent(new CustomEvent("link-palette-changed",{detail:{value:t.target.checked}}))}onLinkBrightnessChanged(t){this.dispatchEvent(new CustomEvent("link-brightness-changed",{detail:{value:t.target.checked}}))}get availablePalettes(){let t=[];return this.showNightPalette&&t.push("night"),this.showDuskPalette&&t.push("dusk"),this.showDayPalette&&t.push("day"),this.showBrightPalette&&t.push("bright"),t}get canIncreasePalette(){let t=this.availablePalettes,e=t.indexOf(this.palette);return e>=0&&e<t.length-1}get canDecreasePalette(){return this.availablePalettes.indexOf(this.palette)>0}nextPalette(){if(this.canIncreasePalette){let t=this.availablePalettes,e=t.indexOf(this.palette);this.palette=t[e+1],this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}}))}}previousPalette(){if(this.canDecreasePalette){let t=this.availablePalettes,e=t.indexOf(this.palette);this.palette=t[e-1],this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}}))}}renderBrightness(){let t=this.variant==="tabbed"?f:c`<div class="title-container">
            <h3>${ae("Brilliance")}</h3>
          </div>`,e=this.brightness.toString().length+.5*this.brightnessUnit.length;return c`${t}
      <div class="content-container brilliance">
        ${this.variant==="compact"?c` <obc-slider
              value=${this.brightness}
              @value=${this.handleBrightnessChanged}
              min="0"
              max=${this.brightnessMax}
              variant=${Vt.Normal}
              haslefticon
              hasrighticon
            >
              <obi-display-brilliance-low
                slot="icon-left"
              ></obi-display-brilliance-low>
              <obi-display-brilliance-proposal
                slot="icon-right"
              ></obi-display-brilliance-proposal>
            </obc-slider>`:c`
              <div class="value-container">
                <div class="value-label-container">
                  <obi-display-brilliance-proposal
                    class="icon"
                  ></obi-display-brilliance-proposal>
                  <div class="label-container" style="width: ${e}ch">
                    <div class="value">${this.brightness.toFixed(0)}</div>
                    <div class="unit">${this.brightnessUnit}</div>
                  </div>
                </div>
                <div class="value-slider-container">
                  ${this.brightnessInputVariant==="buttons"?c`
                        <obc-slider
                          value=${this.brightness}
                          variant=${Vt.NoInput}
                          min="0"
                          max=${this.brightnessMax}
                        ></obc-slider>
                      `:c`
                        <obc-slider
                          value=${this.brightness}
                          variant=${Vt.Enhanced}
                          @value=${this.handleBrightnessChanged}
                          min="0"
                          max=${this.brightnessMax}
                        ></obc-slider>
                      `}
                </div>
              </div>
              ${this.brightnessInputVariant==="buttons"?c`
                    <div class="icon-button-container">
                      <obc-button
                        segmentPosition="start"
                        fullWidth
                        ?disabled=${!this.canDecreaseBrightness}
                        class=${this.canDecreaseBrightness?"":"disabled"}
                        @click=${()=>this.increaseBrightness(-this.brightnessMajorStep)}
                      >
                        <obi-chevron-double-left-google
                          class="btn-icon"
                        ></obi-chevron-double-left-google>
                      </obc-button>
                      <obc-button
                        segmentPosition="middle"
                        fullWidth
                        ?disabled=${!this.canDecreaseBrightness}
                        class=${this.canDecreaseBrightness?"":"disabled"}
                        @click=${()=>this.increaseBrightness(-this.brightnessMinorStep)}
                      >
                        <obi-chevron-left-google
                          class="btn-icon"
                        ></obi-chevron-left-google>
                      </obc-button>
                      <obc-button
                        segmentPosition="middle"
                        fullWidth
                        ?disabled=${!this.canIncreaseBrightness}
                        class=${this.canIncreaseBrightness?"":"disabled"}
                        @click=${()=>this.increaseBrightness(this.brightnessMinorStep)}
                      >
                        <obi-chevron-right-google
                          class="btn-icon"
                        ></obi-chevron-right-google>
                      </obc-button>
                      <obc-button
                        segmentPosition="end"
                        fullWidth
                        ?disabled=${!this.canIncreaseBrightness}
                        class=${this.canIncreaseBrightness?"":"disabled"}
                        @click=${()=>this.increaseBrightness(this.brightnessMajorStep)}
                      >
                        <obi-chevron-double-right-google
                          class="btn-icon"
                        ></obi-chevron-double-right-google>
                      </obc-button>
                    </div>
                  `:f}
            `}
        ${this.showLinkBrightness?c`<obc-toggle-switch
              .label="${ae("Link")}"
              hasicon
              @input=${this.onLinkBrightnessChanged}
            >
              <obi-link slot="icon"></obi-link>
            </obc-toggle-switch>`:f}
      </div>`}get effectivePalette(){let t=this.availablePalettes;return t.includes(this.palette)?this.palette:t[0]}get paletteIcon(){return this.effectivePalette==="night"?c`<obi-palette-night class="icon"></obi-palette-night>`:this.effectivePalette==="dusk"?c`<obi-palette-dusk class="icon"></obi-palette-dusk>`:this.effectivePalette==="day"?c`<obi-palette-day class="icon"></obi-palette-day>`:this.effectivePalette==="bright"?c`<obi-palette-day-bright
        class="icon"
      ></obi-palette-day-bright>`:f}paletteOptions(){let t=[];return this.showNightPalette&&t.push(c`<obc-toggle-button-option value="night" type="icon">
          <obi-palette-night slot="icon"></obi-palette-night>
        </obc-toggle-button-option>`),this.showDuskPalette&&t.push(c`<obc-toggle-button-option value="dusk" type="icon">
          <obi-palette-dusk slot="icon"></obi-palette-dusk>
        </obc-toggle-button-option>`),this.showDayPalette&&t.push(c`<obc-toggle-button-option value="day" type="icon">
          <obi-palette-day slot="icon"></obi-palette-day>
        </obc-toggle-button-option>`),this.showBrightPalette&&t.push(c`<obc-toggle-button-option value="bright" type="icon">
          <obi-palette-day-bright slot="icon"></obi-palette-day-bright>
        </obc-toggle-button-option>`),t}renderPalette(){let t=this.availablePalettes;if(t.length===0)return f;let e={night:ae("Night"),dusk:ae("Dusk"),day:ae("Day"),bright:ae("Bright")},i=e[this.effectivePalette],o=i.length,r=t.indexOf(this.effectivePalette),a=Math.min(r+1,t.length-1),n=Math.max(r-1,0),v=e[t[a]],u=e[t[n]];return c`
      ${this.variant==="tabbed"?f:c`
            <div class="title-container">
              <h3>${ae("Day")}/${ae("Night")}</h3>
            </div>
          `}
      <div
        class="content-container palette ${this.showLinkPalette?"with-link":"without-link"}"
      >
        ${this.variant==="compact"?c` <obc-toggle-button-group
              value=${this.effectivePalette}
              @value=${this.onPaletteChanged}
              variant=${Je.regular}
              type=${ct.icon}
            >
              ${this.paletteOptions()}
            </obc-toggle-button-group>`:c`
              <div class="value-container">
                <div class="value-label-container">
                  ${this.paletteIcon}
                  <div class="label-container" style="width: ${o}ch">
                    <div class="value">${i}</div>
                  </div>
                </div>
                <obc-progress-indicator-dots
                  .totalSteps=${t.length}
                  .currentStep=${r+1}
                ></obc-progress-indicator-dots>
              </div>
              <div class="icon-button-container">
                <obc-button
                  segmentPosition="start"
                  fullWidth
                  showLeadingIcon
                  ?disabled=${!this.canDecreasePalette}
                  class=${this.canDecreasePalette?"":"disabled"}
                  @click=${()=>this.previousPalette()}
                >
                  ${u}
                  <obi-chevron-left-google
                    slot="leading-icon"
                  ></obi-chevron-left-google>
                </obc-button>

                <obc-button
                  segmentPosition="end"
                  fullWidth
                  showTrailingIcon
                  ?disabled=${!this.canIncreasePalette}
                  class=${this.canIncreasePalette?"":"disabled"}
                  @click=${()=>this.nextPalette()}
                >
                  ${v}
                  <obi-chevron-right-google
                    slot="trailing-icon"
                  ></obi-chevron-right-google>
                </obc-button>
              </div>
            `}
        ${this.showLinkPalette?c`<obc-toggle-switch
              .label="${ae("Link")}"
              hasicon
              @input=${this.onLinkPaletteChanged}
            >
              <obi-link slot="icon"></obi-link>
            </obc-toggle-switch>`:f}
      </div>
    `}renderScreenControlLink(){return this.showScreenControlLink?c`
      <div class="footer">
        <obc-navigation-item
          .label="${ae("Screen Control")}"
          @click=${()=>this.handleScreenControlLinkClicked()}
          hasicon
        >
          <obc-user-button slot="icon" static variant="icon" styleType="normal">
            <obi-screen-desk slot="icon"></obi-screen-desk>
          </obc-user-button>
        </obc-navigation-item>
      </div>
    `:f}render(){return this.variant==="tabbed"?c`<obc-tabbed-card class="card" nTabs=${2} hasTabIcons>
        <span slot="tab-title-0">${ae("Brilliance")}</span>
        <obi-display-brilliance-iec
          slot="tab-icon-0"
        ></obi-display-brilliance-iec>
        <span slot="tab-title-1">${ae("Day")}/${ae("Night")}</span>
        <obi-palette-day-night-iec
          slot="tab-icon-1"
        ></obi-palette-day-night-iec>
        <div slot="tab-content-0">
          ${this.renderBrightness()} ${this.renderScreenControlLink()}
        </div>
        <div slot="tab-content-1">
          ${this.renderPalette()} ${this.renderScreenControlLink()}
        </div>
      </obc-tabbed-card>`:c`
        <div class="card ${this.variant}">
          ${this.showBrightness?this.renderBrightness():f}
          ${this.showBrightness&&this.showPalette?c`<div class="divider"></div>`:f}
          ${this.showPalette?this.renderPalette():f}
          ${this.renderScreenControlLink()}
        </div>
      `}handleScreenControlLinkClicked(){this.dispatchEvent(new CustomEvent("screen-control-link-clicked"))}};N.styles=x(ji);q([s({type:String})],N.prototype,"palette",2);q([s({type:Number})],N.prototype,"brightness",2);q([s({type:Boolean})],N.prototype,"showLinkBrightness",2);q([s({type:Boolean})],N.prototype,"showLinkPalette",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showBrightness",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showPalette",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showNightPalette",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showDuskPalette",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showDayPalette",2);q([s({type:Boolean,attribute:!1})],N.prototype,"showBrightPalette",2);q([s({type:String})],N.prototype,"variant",2);q([s({type:String})],N.prototype,"brightnessUnit",2);q([s({type:Number})],N.prototype,"brightnessMax",2);q([s({type:Number})],N.prototype,"brightnessMinorStep",2);q([s({type:Number})],N.prototype,"brightnessMajorStep",2);q([s({type:String})],N.prototype,"brightnessInputVariant",2);q([s({type:Boolean})],N.prototype,"showScreenControlLink",2);N=q([ra(),h("obc-brilliance-menu")],N);var Zl=Object.defineProperty,Sl=Object.getOwnPropertyDescriptor,pa=(t,e,i,o)=>{for(var r=o>1?void 0:o?Sl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Zl(e,i,r),r},Er=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M4 19V17H6V10C6 8.61667 6.41667 7.3875 7.25 6.3125C8.08333 5.2375 9.16667 4.53333 10.5 4.2V3.5C10.5 3.08333 10.6458 2.72917 10.9375 2.4375C11.2292 2.14583 11.5833 2 12 2C12.4167 2 12.7708 2.14583 13.0625 2.4375C13.3542 2.72917 13.5 3.08333 13.5 3.5V4.2C14.8333 4.53333 15.9167 5.2375 16.75 6.3125C17.5833 7.3875 18 8.61667 18 10V17H20V19H4ZM12 22C11.45 22 10.9792 21.8042 10.5875 21.4125C10.1958 21.0208 10 20.55 10 20H14C14 20.55 13.8042 21.0208 13.4125 21.4125C13.0208 21.8042 12.55 22 12 22ZM8 17H16V10C16 8.9 15.6083 7.95833 14.825 7.175C14.0417 6.39167 13.1 6 12 6C10.9 6 9.95833 6.39167 9.175 7.175C8.39167 7.95833 8 8.9 8 10V17Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 19V17H6V10C6 8.61667 6.41667 7.3875 7.25 6.3125C8.08333 5.2375 9.16667 4.53333 10.5 4.2V3.5C10.5 3.08333 10.6458 2.72917 10.9375 2.4375C11.2292 2.14583 11.5833 2 12 2C12.4167 2 12.7708 2.14583 13.0625 2.4375C13.3542 2.72917 13.5 3.08333 13.5 3.5V4.2C14.8333 4.53333 15.9167 5.2375 16.75 6.3125C17.5833 7.3875 18 8.61667 18 10V17H20V19H4ZM12 22C11.45 22 10.9792 21.8042 10.5875 21.4125C10.1958 21.0208 10 20.55 10 20H14C14 20.55 13.8042 21.0208 13.4125 21.4125C13.0208 21.8042 12.55 22 12 22ZM8 17H16V10C16 8.9 15.6083 7.95833 14.825 7.175C14.0417 6.39167 13.1 6 12 6C10.9 6 9.95833 6.39167 9.175 7.175C8.39167 7.95833 8 8.9 8 10V17Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Er.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;pa([s({type:Boolean})],Er.prototype,"useCssColor",2);Er=pa([h("obi-alerts")],Er);var Al=Object.defineProperty,Pl=Object.getOwnPropertyDescriptor,ha=(t,e,i,o)=>{for(var r=o>1?void 0:o?Pl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Al(e,i,r),r},zr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M1.80718 1.3938L0.393188 2.80779L5.5855 8.0001H5.19963C4.07953 8.0001 3.51948 8.0001 3.09165 8.21809C2.71533 8.40983 2.40937 8.71579 2.21762 9.09212C1.99963 9.51994 1.99963 10.08 1.99963 11.2001V12.8001C1.99963 13.9202 1.99963 14.4803 2.21762 14.9081C2.40937 15.2844 2.71533 15.5904 3.09165 15.7821C3.51948 16.0001 4.07953 16.0001 5.19963 16.0001H7.99963L11.2683 19.2687C12.125 20.1255 12.5534 20.5539 12.9212 20.5828C13.2403 20.6079 13.5521 20.4787 13.76 20.2353C13.9996 19.9548 13.9996 19.349 13.9996 18.1374V16.4142L20.1922 22.6068L21.6064 21.1926L13.9996 13.586V5.86284C13.9996 4.65121 13.9996 4.04539 13.76 3.76486C13.5521 3.52145 13.2403 3.39228 12.9212 3.41739C12.5534 3.44634 12.125 3.87472 11.2683 4.73147L8.20663 7.7931L1.80718 1.3938ZM7.5855 10.0001H3.99963C3.99963 10.0001 3.99963 12.438 3.99963 14.0001H8.82806L11.9996 17.1717V14.4142L7.5855 10.0001ZM11.9996 11.586L9.62086 9.2073L11.9996 6.82853V11.586Z" fill="currentColor"/>
<path d="M20.3852 17.1434C20.7544 16.6132 21.0663 16.0436 21.3147 15.444C21.767 14.352 21.9998 13.1817 21.9998 11.9998C21.9998 10.8179 21.767 9.64758 21.3147 8.55565C20.8624 7.46372 20.1995 6.47157 19.3637 5.63584C18.528 4.80011 17.5359 4.13718 16.4439 3.68489C16.2972 3.62413 16.1491 3.56733 15.9998 3.51452V5.67525C16.7228 6.0182 17.3825 6.48298 17.9495 7.05006C18.5995 7.70007 19.1152 8.47174 19.4669 9.32102C19.8187 10.1703 19.9998 11.0805 19.9998 11.9998C19.9998 12.9191 19.8187 13.8293 19.4669 14.6786C19.3198 15.0337 19.1441 15.3753 18.9419 15.7L20.3852 17.1434Z" fill="currentColor"/>
<path d="M17.3801 14.1383L15.9998 12.758V8.5357C16.3019 8.71011 16.5805 8.92366 16.8282 9.17138C17.1996 9.54281 17.4943 9.98377 17.6953 10.4691C17.8963 10.9544 17.9998 11.4745 17.9998 11.9998C17.9998 12.5251 17.8963 13.0452 17.6953 13.5305C17.6076 13.7423 17.5021 13.9456 17.3801 14.1383Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M1.80718 1.3938L0.393188 2.80779L5.5855 8.0001H5.19963C4.07953 8.0001 3.51948 8.0001 3.09165 8.21809C2.71533 8.40983 2.40937 8.71579 2.21762 9.09212C1.99963 9.51994 1.99963 10.08 1.99963 11.2001V12.8001C1.99963 13.9202 1.99963 14.4803 2.21762 14.9081C2.40937 15.2844 2.71533 15.5904 3.09165 15.7821C3.51948 16.0001 4.07953 16.0001 5.19963 16.0001H7.99963L11.2683 19.2687C12.125 20.1255 12.5534 20.5539 12.9212 20.5828C13.2403 20.6079 13.5521 20.4787 13.76 20.2353C13.9996 19.9548 13.9996 19.349 13.9996 18.1374V16.4142L20.1922 22.6068L21.6064 21.1926L13.9996 13.586V5.86284C13.9996 4.65121 13.9996 4.04539 13.76 3.76486C13.5521 3.52145 13.2403 3.39228 12.9212 3.41739C12.5534 3.44634 12.125 3.87472 11.2683 4.73147L8.20663 7.7931L1.80718 1.3938ZM7.5855 10.0001H3.99963C3.99963 10.0001 3.99963 12.438 3.99963 14.0001H8.82806L11.9996 17.1717V14.4142L7.5855 10.0001ZM11.9996 11.586L9.62086 9.2073L11.9996 6.82853V11.586Z" style="fill: var(--element-active-color)"/>
<path d="M20.3852 17.1434C20.7544 16.6132 21.0663 16.0436 21.3147 15.444C21.767 14.352 21.9998 13.1817 21.9998 11.9998C21.9998 10.8179 21.767 9.64758 21.3147 8.55565C20.8624 7.46372 20.1995 6.47157 19.3637 5.63584C18.528 4.80011 17.5359 4.13718 16.4439 3.68489C16.2972 3.62413 16.1491 3.56733 15.9998 3.51452V5.67525C16.7228 6.0182 17.3825 6.48298 17.9495 7.05006C18.5995 7.70007 19.1152 8.47174 19.4669 9.32102C19.8187 10.1703 19.9998 11.0805 19.9998 11.9998C19.9998 12.9191 19.8187 13.8293 19.4669 14.6786C19.3198 15.0337 19.1441 15.3753 18.9419 15.7L20.3852 17.1434Z" style="fill: var(--element-active-color)"/>
<path d="M17.3801 14.1383L15.9998 12.758V8.5357C16.3019 8.71011 16.5805 8.92366 16.8282 9.17138C17.1996 9.54281 17.4943 9.98377 17.6953 10.4691C17.8963 10.9544 17.9998 11.4745 17.9998 11.9998C17.9998 12.5251 17.8963 13.0452 17.6953 13.5305C17.6076 13.7423 17.5021 13.9456 17.3801 14.1383Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};zr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ha([s({type:Boolean})],zr.prototype,"useCssColor",2);zr=ha([h("obi-sound-muted")],zr);var Ol=Object.defineProperty,Bl=Object.getOwnPropertyDescriptor,ua=(t,e,i,o)=>{for(var r=o>1?void 0:o?Bl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ol(e,i,r),r},Dr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M10 12C8.9 12 7.95833 11.6083 7.175 10.825C6.39167 10.0417 6 9.1 6 8C6 6.9 6.39167 5.95833 7.175 5.175C7.95833 4.39167 8.9 4 10 4C11.1 4 12.0417 4.39167 12.825 5.175C13.6083 5.95833 14 6.9 14 8C14 9.1 13.6083 10.0417 12.825 10.825C12.0417 11.6083 11.1 12 10 12ZM2 20V17.2C2 16.65 2.14167 16.1333 2.425 15.65C2.70833 15.1667 3.1 14.8 3.6 14.55C4.45 14.1167 5.40833 13.75 6.475 13.45C7.54167 13.15 8.71667 13 10 13H10.35C10.45 13 10.55 13.0167 10.65 13.05C10.5167 13.35 10.4042 13.6625 10.3125 13.9875C10.2208 14.3125 10.15 14.65 10.1 15H10C8.81667 15 7.75417 15.15 6.8125 15.45C5.87083 15.75 5.1 16.05 4.5 16.35C4.35 16.4333 4.22917 16.55 4.1375 16.7C4.04583 16.85 4 17.0167 4 17.2V18H10.3C10.4 18.35 10.5333 18.6958 10.7 19.0375C10.8667 19.3792 11.05 19.7 11.25 20H2ZM16 21L15.7 19.5C15.5 19.4167 15.3125 19.3292 15.1375 19.2375C14.9625 19.1458 14.7833 19.0333 14.6 18.9L13.15 19.35L12.15 17.65L13.3 16.65C13.2667 16.4167 13.25 16.2 13.25 16C13.25 15.8 13.2667 15.5833 13.3 15.35L12.15 14.35L13.15 12.65L14.6 13.1C14.7833 12.9667 14.9625 12.8542 15.1375 12.7625C15.3125 12.6708 15.5 12.5833 15.7 12.5L16 11H18L18.3 12.5C18.5 12.5833 18.6875 12.675 18.8625 12.775C19.0375 12.875 19.2167 13 19.4 13.15L20.85 12.65L21.85 14.4L20.7 15.4C20.7333 15.6 20.75 15.8083 20.75 16.025C20.75 16.2417 20.7333 16.45 20.7 16.65L21.85 17.65L20.85 19.35L19.4 18.9C19.2167 19.0333 19.0375 19.1458 18.8625 19.2375C18.6875 19.3292 18.5 19.4167 18.3 19.5L18 21H16ZM17 18C17.55 18 18.0208 17.8042 18.4125 17.4125C18.8042 17.0208 19 16.55 19 16C19 15.45 18.8042 14.9792 18.4125 14.5875C18.0208 14.1958 17.55 14 17 14C16.45 14 15.9792 14.1958 15.5875 14.5875C15.1958 14.9792 15 15.45 15 16C15 16.55 15.1958 17.0208 15.5875 17.4125C15.9792 17.8042 16.45 18 17 18ZM10 10C10.55 10 11.0208 9.80417 11.4125 9.4125C11.8042 9.02083 12 8.55 12 8C12 7.45 11.8042 6.97917 11.4125 6.5875C11.0208 6.19583 10.55 6 10 6C9.45 6 8.97917 6.19583 8.5875 6.5875C8.19583 6.97917 8 7.45 8 8C8 8.55 8.19583 9.02083 8.5875 9.4125C8.97917 9.80417 9.45 10 10 10Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 12C8.9 12 7.95833 11.6083 7.175 10.825C6.39167 10.0417 6 9.1 6 8C6 6.9 6.39167 5.95833 7.175 5.175C7.95833 4.39167 8.9 4 10 4C11.1 4 12.0417 4.39167 12.825 5.175C13.6083 5.95833 14 6.9 14 8C14 9.1 13.6083 10.0417 12.825 10.825C12.0417 11.6083 11.1 12 10 12ZM2 20V17.2C2 16.65 2.14167 16.1333 2.425 15.65C2.70833 15.1667 3.1 14.8 3.6 14.55C4.45 14.1167 5.40833 13.75 6.475 13.45C7.54167 13.15 8.71667 13 10 13H10.35C10.45 13 10.55 13.0167 10.65 13.05C10.5167 13.35 10.4042 13.6625 10.3125 13.9875C10.2208 14.3125 10.15 14.65 10.1 15H10C8.81667 15 7.75417 15.15 6.8125 15.45C5.87083 15.75 5.1 16.05 4.5 16.35C4.35 16.4333 4.22917 16.55 4.1375 16.7C4.04583 16.85 4 17.0167 4 17.2V18H10.3C10.4 18.35 10.5333 18.6958 10.7 19.0375C10.8667 19.3792 11.05 19.7 11.25 20H2ZM16 21L15.7 19.5C15.5 19.4167 15.3125 19.3292 15.1375 19.2375C14.9625 19.1458 14.7833 19.0333 14.6 18.9L13.15 19.35L12.15 17.65L13.3 16.65C13.2667 16.4167 13.25 16.2 13.25 16C13.25 15.8 13.2667 15.5833 13.3 15.35L12.15 14.35L13.15 12.65L14.6 13.1C14.7833 12.9667 14.9625 12.8542 15.1375 12.7625C15.3125 12.6708 15.5 12.5833 15.7 12.5L16 11H18L18.3 12.5C18.5 12.5833 18.6875 12.675 18.8625 12.775C19.0375 12.875 19.2167 13 19.4 13.15L20.85 12.65L21.85 14.4L20.7 15.4C20.7333 15.6 20.75 15.8083 20.75 16.025C20.75 16.2417 20.7333 16.45 20.7 16.65L21.85 17.65L20.85 19.35L19.4 18.9C19.2167 19.0333 19.0375 19.1458 18.8625 19.2375C18.6875 19.3292 18.5 19.4167 18.3 19.5L18 21H16ZM17 18C17.55 18 18.0208 17.8042 18.4125 17.4125C18.8042 17.0208 19 16.55 19 16C19 15.45 18.8042 14.9792 18.4125 14.5875C18.0208 14.1958 17.55 14 17 14C16.45 14 15.9792 14.1958 15.5875 14.5875C15.1958 14.9792 15 15.45 15 16C15 16.55 15.1958 17.0208 15.5875 17.4125C15.9792 17.8042 16.45 18 17 18ZM10 10C10.55 10 11.0208 9.80417 11.4125 9.4125C11.8042 9.02083 12 8.55 12 8C12 7.45 11.8042 6.97917 11.4125 6.5875C11.0208 6.19583 10.55 6 10 6C9.45 6 8.97917 6.19583 8.5875 6.5875C8.19583 6.97917 8 7.45 8 8C8 8.55 8.19583 9.02083 8.5875 9.4125C8.97917 9.80417 9.45 10 10 10Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Dr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ua([s({type:Boolean})],Dr.prototype,"useCssColor",2);Dr=ua([h("obi-settings-user-proposal")],Dr);var Tl=Object.defineProperty,El=Object.getOwnPropertyDescriptor,va=(t,e,i,o)=>{for(var r=o>1?void 0:o?El(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Tl(e,i,r),r},Ir=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 13L16 17H13V22H11V17H8L12 13Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 11.5607L15.5303 8.03033L14.4697 6.96967L12 9.43934L9.53033 6.96967L8.46967 8.03033L12 11.5607Z" fill="currentColor"/>
<path d="M13 5.5C13 6.05228 12.5523 6.5 12 6.5C11.4477 6.5 11 6.05228 11 5.5C11 4.94772 11.4477 4.5 12 4.5C12.5523 4.5 13 4.94772 13 5.5Z" fill="currentColor"/>
<path d="M13 2C13 2.55228 12.5523 3 12 3C11.4477 3 11 2.55228 11 2C11 1.44772 11.4477 1 12 1C12.5523 1 13 1.44772 13 2Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 13L16 17H13V22H11V17H8L12 13Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 11.5607L15.5303 8.03033L14.4697 6.96967L12 9.43934L9.53033 6.96967L8.46967 8.03033L12 11.5607Z" style="fill: var(--element-active-color)"/>
<path d="M13 5.5C13 6.05228 12.5523 6.5 12 6.5C11.4477 6.5 11 6.05228 11 5.5C11 4.94772 11.4477 4.5 12 4.5C12.5523 4.5 13 4.94772 13 5.5Z" style="fill: var(--element-active-color)"/>
<path d="M13 2C13 2.55228 12.5523 3 12 3C11.4477 3 11 2.55228 11 2C11 1.44772 11.4477 1 12 1C12.5523 1 13 1.44772 13 2Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ir.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;va([s({type:Boolean})],Ir.prototype,"useCssColor",2);Ir=va([h("obi-collision-avoidance-head-on")],Ir);var zl=Object.defineProperty,Dl=Object.getOwnPropertyDescriptor,ma=(t,e,i,o)=>{for(var r=o>1?void 0:o?Dl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&zl(e,i,r),r},Rr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8 19.5V4.5L20 12L8 19.5Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8 19.5V4.5L20 12L8 19.5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Rr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ma([s({type:Boolean})],Rr.prototype,"useCssColor",2);Rr=ma([h("obi-media-play")],Rr);var Il=Object.defineProperty,Rl=Object.getOwnPropertyDescriptor,fa=(t,e,i,o)=>{for(var r=o>1?void 0:o?Rl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Il(e,i,r),r},jr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M10 5H6V19H10V5Z" fill="currentColor"/>
<path d="M18 5H13.9967V19H18V5Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 5H6V19H10V5Z" style="fill: var(--element-active-color)"/>
<path d="M18 5H13.9967V19H18V5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};jr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;fa([s({type:Boolean})],jr.prototype,"useCssColor",2);jr=fa([h("obi-media-pause")],jr);var jl=Object.defineProperty,Nl=Object.getOwnPropertyDescriptor,ga=(t,e,i,o)=>{for(var r=o>1?void 0:o?Nl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&jl(e,i,r),r},Nr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M17 5V19H20V5H17Z" fill="currentColor"/>
<path d="M4 5V19L15 12L4 5Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M17 5V19H20V5H17Z" style="fill: var(--element-active-color)"/>
<path d="M4 5V19L15 12L4 5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Nr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ga([s({type:Boolean})],Nr.prototype,"useCssColor",2);Nr=ga([h("obi-media-skip-next")],Nr);var Fl=Object.defineProperty,Ul=Object.getOwnPropertyDescriptor,ba=(t,e,i,o)=>{for(var r=o>1?void 0:o?Ul(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Fl(e,i,r),r},Fr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C15.866 5 19 8.13401 19 12C19 15.866 15.866 19 12 19C10.067 19 8.317 18.2165 7.05025 16.9497L5.63604 18.364C7.26472 19.9926 9.51472 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C9.17273 3 6.64996 4.30367 5 6.34267V3H3V10H10V8H6.25469C7.51964 6.18652 9.62125 5 12 5Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C15.866 5 19 8.13401 19 12C19 15.866 15.866 19 12 19C10.067 19 8.317 18.2165 7.05025 16.9497L5.63604 18.364C7.26472 19.9926 9.51472 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C9.17273 3 6.64996 4.30367 5 6.34267V3H3V10H10V8H6.25469C7.51964 6.18652 9.62125 5 12 5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Fr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ba([s({type:Boolean})],Fr.prototype,"useCssColor",2);Fr=ba([h("obi-reset")],Fr);var Wl=Object.defineProperty,Gl=Object.getOwnPropertyDescriptor,Ca=(t,e,i,o)=>{for(var r=o>1?void 0:o?Gl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Wl(e,i,r),r},Ur=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5 19V5V16.35V14.225V19ZM5 21C4.45 21 3.97917 20.8042 3.5875 20.4125C3.19583 20.0208 3 19.55 3 19V5C3 4.45 3.19583 3.97917 3.5875 3.5875C3.97917 3.19583 4.45 3 5 3H19C19.55 3 20.0208 3.19583 20.4125 3.5875C20.8042 3.97917 21 4.45 21 5V13H19V5H5V19H12V21H5ZM17.35 22L13.8 18.45L15.225 17.05L17.35 19.175L21.6 14.925L23 16.35L17.35 22ZM8 13C8.28333 13 8.52083 12.9042 8.7125 12.7125C8.90417 12.5208 9 12.2833 9 12C9 11.7167 8.90417 11.4792 8.7125 11.2875C8.52083 11.0958 8.28333 11 8 11C7.71667 11 7.47917 11.0958 7.2875 11.2875C7.09583 11.4792 7 11.7167 7 12C7 12.2833 7.09583 12.5208 7.2875 12.7125C7.47917 12.9042 7.71667 13 8 13ZM8 9C8.28333 9 8.52083 8.90417 8.7125 8.7125C8.90417 8.52083 9 8.28333 9 8C9 7.71667 8.90417 7.47917 8.7125 7.2875C8.52083 7.09583 8.28333 7 8 7C7.71667 7 7.47917 7.09583 7.2875 7.2875C7.09583 7.47917 7 7.71667 7 8C7 8.28333 7.09583 8.52083 7.2875 8.7125C7.47917 8.90417 7.71667 9 8 9ZM11 13H17V11H11V13ZM11 9H17V7H11V9Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5 19V5V16.35V14.225V19ZM5 21C4.45 21 3.97917 20.8042 3.5875 20.4125C3.19583 20.0208 3 19.55 3 19V5C3 4.45 3.19583 3.97917 3.5875 3.5875C3.97917 3.19583 4.45 3 5 3H19C19.55 3 20.0208 3.19583 20.4125 3.5875C20.8042 3.97917 21 4.45 21 5V13H19V5H5V19H12V21H5ZM17.35 22L13.8 18.45L15.225 17.05L17.35 19.175L21.6 14.925L23 16.35L17.35 22ZM8 13C8.28333 13 8.52083 12.9042 8.7125 12.7125C8.90417 12.5208 9 12.2833 9 12C9 11.7167 8.90417 11.4792 8.7125 11.2875C8.52083 11.0958 8.28333 11 8 11C7.71667 11 7.47917 11.0958 7.2875 11.2875C7.09583 11.4792 7 11.7167 7 12C7 12.2833 7.09583 12.5208 7.2875 12.7125C7.47917 12.9042 7.71667 13 8 13ZM8 9C8.28333 9 8.52083 8.90417 8.7125 8.7125C8.90417 8.52083 9 8.28333 9 8C9 7.71667 8.90417 7.47917 8.7125 7.2875C8.52083 7.09583 8.28333 7 8 7C7.71667 7 7.47917 7.09583 7.2875 7.2875C7.09583 7.47917 7 7.71667 7 8C7 8.28333 7.09583 8.52083 7.2875 8.7125C7.47917 8.90417 7.71667 9 8 9ZM11 13H17V11H11V13ZM11 9H17V7H11V9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ur.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ca([s({type:Boolean})],Ur.prototype,"useCssColor",2);Ur=Ca([h("obi-list-alt-check-google")],Ur);var ql=Object.defineProperty,Xl=Object.getOwnPropertyDescriptor,ya=(t,e,i,o)=>{for(var r=o>1?void 0:o?Xl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&ql(e,i,r),r},Wr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" fill="currentColor"/>
<path d="M15.0623 7.5L12.0311 4.5L9 7.5H11.0311V10.5H13.0311V7.5H15.0623Z" fill="currentColor"/>
<path d="M16 8.93782L13 11.9689L16 15V12.9689H19V10.9689H16V8.93782Z" fill="currentColor"/>
<path d="M8 15.0622L11 12.0311L8 9V11.0311H5V13.0311H8V15.0622Z" fill="currentColor"/>
<path d="M9.00012 16.5L12.0312 19.5L15.0623 16.5H13.0312V13.5H11.0312V16.5H9.00012Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" style="fill: var(--element-active-color)"/>
<path d="M15.0623 7.5L12.0311 4.5L9 7.5H11.0311V10.5H13.0311V7.5H15.0623Z" style="fill: var(--element-active-color)"/>
<path d="M16 8.93782L13 11.9689L16 15V12.9689H19V10.9689H16V8.93782Z" style="fill: var(--element-active-color)"/>
<path d="M8 15.0622L11 12.0311L8 9V11.0311H5V13.0311H8V15.0622Z" style="fill: var(--element-active-color)"/>
<path d="M9.00012 16.5L12.0312 19.5L15.0623 16.5H13.0312V13.5H11.0312V16.5H9.00012Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Wr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ya([s({type:Boolean})],Wr.prototype,"useCssColor",2);Wr=ya([h("obi-router-component")],Wr);var Yl=Object.defineProperty,Jl=Object.getOwnPropertyDescriptor,wa=(t,e,i,o)=>{for(var r=o>1?void 0:o?Jl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Yl(e,i,r),r},Gr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M15.8506 12.4062C17.4207 10.8362 19.6451 10.3174 21.6465 10.8516L21.6475 10.8525C22.182 12.8542 21.6641 15.079 20.0938 16.6494L14.5254 22.2178L10.2822 17.9746L15.8506 12.4062ZM19.8428 12.6562C18.9025 12.7148 17.9811 13.1039 17.2646 13.8203L13.1104 17.9746L14.5244 19.3887L18.6787 15.2354C19.3954 14.5187 19.7844 13.5968 19.8428 12.6562ZM9 14H7V10H9V14ZM6 9H2V7H6V9ZM14 9H10V7H14V9ZM9 2V6H7V2H9Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M15.8506 12.4062C17.4207 10.8362 19.6451 10.3174 21.6465 10.8516L21.6475 10.8525C22.182 12.8542 21.6641 15.079 20.0938 16.6494L14.5254 22.2178L10.2822 17.9746L15.8506 12.4062ZM19.8428 12.6562C18.9025 12.7148 17.9811 13.1039 17.2646 13.8203L13.1104 17.9746L14.5244 19.3887L18.6787 15.2354C19.3954 14.5187 19.7844 13.5968 19.8428 12.6562ZM9 14H7V10H9V14ZM6 9H2V7H6V9ZM14 9H10V7H14V9ZM9 2V6H7V2H9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Gr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;wa([s({type:Boolean})],Gr.prototype,"useCssColor",2);Gr=wa([h("obi-center-off-iec")],Gr);var Ql=Object.defineProperty,Kl=Object.getOwnPropertyDescriptor,La=(t,e,i,o)=>{for(var r=o>1?void 0:o?Kl(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&Ql(e,i,r),r},qr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M10.2036 5.55373C11.774 3.98336 13.9983 3.46545 16 4C16.5346 6.0017 16.0166 8.226 14.4463 9.79637L7.93843 16.3042L3.69579 12.0616L10.2036 5.55373ZM11.2643 6.61439C12.2058 5.67289 13.4612 5.23456 14.6969 5.30313C14.7654 6.53876 14.3271 7.79421 13.3856 8.73571L7.93843 14.1829L5.81711 12.0616L11.2643 6.61439Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9564 16.9999C20.6132 16.9999 21.9564 15.6568 21.9564 13.9999C21.9564 12.343 20.6132 10.9999 18.9564 10.9999C17.2995 10.9999 15.9564 12.343 15.9564 13.9999C15.9564 15.6568 17.2995 16.9999 18.9564 16.9999Z" fill="currentColor"/>
<path d="M14.2736 20.0002L15.6878 18.586L14.2736 17.1717L12.8594 18.586L11.4452 17.1717L10.7381 22.1215L15.6878 21.4144L14.2736 20.0002Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M10.2036 5.55373C11.774 3.98336 13.9983 3.46545 16 4C16.5346 6.0017 16.0166 8.226 14.4463 9.79637L7.93843 16.3042L3.69579 12.0616L10.2036 5.55373ZM11.2643 6.61439C12.2058 5.67289 13.4612 5.23456 14.6969 5.30313C14.7654 6.53876 14.3271 7.79421 13.3856 8.73571L7.93843 14.1829L5.81711 12.0616L11.2643 6.61439Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9564 16.9999C20.6132 16.9999 21.9564 15.6568 21.9564 13.9999C21.9564 12.343 20.6132 10.9999 18.9564 10.9999C17.2995 10.9999 15.9564 12.343 15.9564 13.9999C15.9564 15.6568 17.2995 16.9999 18.9564 16.9999Z" style="fill: var(--element-active-color)"/>
<path d="M14.2736 20.0002L15.6878 18.586L14.2736 17.1717L12.8594 18.586L11.4452 17.1717L10.7381 22.1215L15.6878 21.4144L14.2736 20.0002Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};qr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;La([s({type:Boolean})],qr.prototype,"useCssColor",2);qr=La([h("obi-motion-relative-proposal")],qr);var e2=Object.defineProperty,t2=Object.getOwnPropertyDescriptor,ka=(t,e,i,o)=>{for(var r=o>1?void 0:o?t2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&e2(e,i,r),r},Xr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M6.66517 5.99945C5.44261 7.222 4.79212 8.78595 4.6814 10.3822H1.35974L5.51182 14.5343L9.66389 10.3822L6.32378 10.3822C6.42988 9.20577 6.91891 8.05242 7.81852 7.1528C9.45628 5.51504 11.906 5.19671 13.8621 6.18398L14.591 4.73537C12.0213 3.439 8.81041 3.85421 6.66517 5.99945Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M8.82261 14.5019C10.1312 13.1934 11.9847 12.7618 13.6528 13.2073C14.0982 14.8754 13.6667 16.7289 12.3581 18.0375L7.64234 22.7533L4.10681 19.2177L8.82261 14.5019ZM12.3225 14.5376C11.4371 14.5464 10.5568 14.889 9.88327 15.5626L6.22813 19.2177L7.64234 20.6319L11.2975 16.9768C11.9711 16.3032 12.3137 15.4229 12.3225 14.5376Z" fill="currentColor"/>
<path d="M22.8451 4.01494C21.1771 3.56944 19.3236 4.00097 18.015 5.30955L13.2992 10.0253L16.8347 13.5609L21.5505 8.84508C22.8591 7.53651 23.2906 5.68299 22.8451 4.01494Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M6.66517 5.99945C5.44261 7.222 4.79212 8.78595 4.6814 10.3822H1.35974L5.51182 14.5343L9.66389 10.3822L6.32378 10.3822C6.42988 9.20577 6.91891 8.05242 7.81852 7.1528C9.45628 5.51504 11.906 5.19671 13.8621 6.18398L14.591 4.73537C12.0213 3.439 8.81041 3.85421 6.66517 5.99945Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M8.82261 14.5019C10.1312 13.1934 11.9847 12.7618 13.6528 13.2073C14.0982 14.8754 13.6667 16.7289 12.3581 18.0375L7.64234 22.7533L4.10681 19.2177L8.82261 14.5019ZM12.3225 14.5376C11.4371 14.5464 10.5568 14.889 9.88327 15.5626L6.22813 19.2177L7.64234 20.6319L11.2975 16.9768C11.9711 16.3032 12.3137 15.4229 12.3225 14.5376Z" style="fill: var(--element-active-color)"/>
<path d="M22.8451 4.01494C21.1771 3.56944 19.3236 4.00097 18.015 5.30955L13.2992 10.0253L16.8347 13.5609L21.5505 8.84508C22.8591 7.53651 23.2906 5.68299 22.8451 4.01494Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Xr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;ka([s({type:Boolean})],Xr.prototype,"useCssColor",2);Xr=ka([h("obi-motion-tm-reset-proposal-2")],Xr);var r2=Object.defineProperty,o2=Object.getOwnPropertyDescriptor,Ma=(t,e,i,o)=>{for(var r=o>1?void 0:o?o2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&r2(e,i,r),r},Yr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21.05L3 14.05L4.65 12.8L12 18.5L19.35 12.8L21 14.05L12 21.05ZM12 16L3 9L12 2L21 9L12 16ZM12 13.45L17.75 9L12 4.55L6.25 9L12 13.45Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21.05L3 14.05L4.65 12.8L12 18.5L19.35 12.8L21 14.05L12 21.05ZM12 16L3 9L12 2L21 9L12 16ZM12 13.45L17.75 9L12 4.55L6.25 9L12 13.45Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Yr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ma([s({type:Boolean})],Yr.prototype,"useCssColor",2);Yr=Ma([h("obi-chart-layers")],Yr);var i2=Object.defineProperty,a2=Object.getOwnPropertyDescriptor,xa=(t,e,i,o)=>{for(var r=o>1?void 0:o?a2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&i2(e,i,r),r},Jr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M4 8V4H8V2H4C2.89543 2 2 2.89543 2 4V8H4Z" fill="currentColor"/>
<path d="M4 16H2V20C2 21.1046 2.89543 22 4 22H8V20H4V16Z" fill="currentColor"/>
<path d="M16 20V22H20C21.1046 22 22 21.1046 22 20V16H20V20H16Z" fill="currentColor"/>
<path d="M20 8H22V4.00002C22 2.89546 21.1046 2.00003 20 2.00002L16 2V4H20V8Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 8V4H8V2H4C2.89543 2 2 2.89543 2 4V8H4Z" style="fill: var(--element-active-color)"/>
<path d="M4 16H2V20C2 21.1046 2.89543 22 4 22H8V20H4V16Z" style="fill: var(--element-active-color)"/>
<path d="M16 20V22H20C21.1046 22 22 21.1046 22 20V16H20V20H16Z" style="fill: var(--element-active-color)"/>
<path d="M20 8H22V4.00002C22 2.89546 21.1046 2.00003 20 2.00002L16 2V4H20V8Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Jr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;xa([s({type:Boolean})],Jr.prototype,"useCssColor",2);Jr=xa([h("obi-target-select-iec")],Jr);var n2=Object.defineProperty,s2=Object.getOwnPropertyDescriptor,Ha=(t,e,i,o)=>{for(var r=o>1?void 0:o?s2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&n2(e,i,r),r},Qr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7 19.4989C7 20.8797 5.88071 21.9989 4.5 21.9989C3.11929 21.9989 2 20.8797 2 19.4989C2 18.1182 3.11929 16.9989 4.5 16.9989C5.88071 16.9989 7 18.1182 7 19.4989Z" fill="currentColor"/>
<path d="M15.9602 6.62457L17.3744 5.21036L18.7886 6.62457L17.3744 8.03879L15.9602 6.62457Z" fill="currentColor"/>
<path d="M18.7886 3.79615L20.2028 2.38193L21.617 3.79615L20.2028 5.21036L18.7886 3.79615Z" fill="currentColor"/>
<path d="M13.1317 9.453L14.5459 8.03879L15.9602 9.453L14.5459 10.8672L13.1317 9.453Z" fill="currentColor"/>
<path d="M10.3033 12.2814L11.7175 10.8672L13.1317 12.2814L11.7175 13.6956L10.3033 12.2814Z" fill="currentColor"/>
<path d="M7.47487 15.1099L8.88909 13.6956L10.3033 15.1099L8.88909 16.5241L7.47487 15.1099Z" fill="currentColor"/>
<path d="M20.499 18.4989H22.499V20.4989H20.499V18.4989Z" fill="currentColor"/>
<path d="M19.6951 14.3922L21.6269 13.8745L22.1445 15.8064L20.2127 16.324L19.6951 14.3922Z" fill="currentColor"/>
<path d="M17.8555 10.6335L19.5876 9.63346L20.5876 11.3655L18.8555 12.3655L17.8555 10.6335Z" fill="currentColor"/>
<path d="M11.6331 5.14344L12.6331 3.41139L14.3651 4.41139L13.3651 6.14344L11.6331 5.14344Z" fill="currentColor"/>
<path d="M7.67474 3.78642L8.19238 1.85456L10.1242 2.3722L9.60659 4.30405L7.67474 3.78642Z" fill="currentColor"/>
<path d="M3.49967 3.5L3.49967 1.5L5.49967 1.5V3.5H3.49967Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7 19.4989C7 20.8797 5.88071 21.9989 4.5 21.9989C3.11929 21.9989 2 20.8797 2 19.4989C2 18.1182 3.11929 16.9989 4.5 16.9989C5.88071 16.9989 7 18.1182 7 19.4989Z" style="fill: var(--element-active-color)"/>
<path d="M15.9602 6.62457L17.3744 5.21036L18.7886 6.62457L17.3744 8.03879L15.9602 6.62457Z" style="fill: var(--element-active-color)"/>
<path d="M18.7886 3.79615L20.2028 2.38193L21.617 3.79615L20.2028 5.21036L18.7886 3.79615Z" style="fill: var(--element-active-color)"/>
<path d="M13.1317 9.453L14.5459 8.03879L15.9602 9.453L14.5459 10.8672L13.1317 9.453Z" style="fill: var(--element-active-color)"/>
<path d="M10.3033 12.2814L11.7175 10.8672L13.1317 12.2814L11.7175 13.6956L10.3033 12.2814Z" style="fill: var(--element-active-color)"/>
<path d="M7.47487 15.1099L8.88909 13.6956L10.3033 15.1099L8.88909 16.5241L7.47487 15.1099Z" style="fill: var(--element-active-color)"/>
<path d="M20.499 18.4989H22.499V20.4989H20.499V18.4989Z" style="fill: var(--element-active-color)"/>
<path d="M19.6951 14.3922L21.6269 13.8745L22.1445 15.8064L20.2127 16.324L19.6951 14.3922Z" style="fill: var(--element-active-color)"/>
<path d="M17.8555 10.6335L19.5876 9.63346L20.5876 11.3655L18.8555 12.3655L17.8555 10.6335Z" style="fill: var(--element-active-color)"/>
<path d="M11.6331 5.14344L12.6331 3.41139L14.3651 4.41139L13.3651 6.14344L11.6331 5.14344Z" style="fill: var(--element-active-color)"/>
<path d="M7.67474 3.78642L8.19238 1.85456L10.1242 2.3722L9.60659 4.30405L7.67474 3.78642Z" style="fill: var(--element-active-color)"/>
<path d="M3.49967 3.5L3.49967 1.5L5.49967 1.5V3.5H3.49967Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Qr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ha([s({type:Boolean})],Qr.prototype,"useCssColor",2);Qr=Ha([h("obi-radar-electronic-range-and-bearing-proposal")],Qr);var l2=Object.defineProperty,c2=Object.getOwnPropertyDescriptor,$a=(t,e,i,o)=>{for(var r=o>1?void 0:o?c2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&l2(e,i,r),r},Kr=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M9.6645 14C9.13165 14 8.86523 14 8.72839 14.1092C8.60938 14.2042 8.54015 14.3483 8.54031 14.5005C8.5405 14.6756 8.70694 14.8837 9.03981 15.2998L12 19L14.9602 15.2998C15.2931 14.8837 15.4595 14.6756 15.4597 14.5005C15.4599 14.3483 15.3906 14.2042 15.2716 14.1092C15.1348 14 14.8684 14 14.3355 14H9.6645Z" fill="currentColor"/>
<path d="M2 22H5V20H2V22Z" fill="currentColor"/>
<path d="M7 22H11V20H7V22Z" fill="currentColor"/>
<path d="M13 22H17V20H13V22Z" fill="currentColor"/>
<path d="M19 22H22V20H19V22Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.97034 6.60754C6.8857 6.72976 6.84338 6.79087 6.82134 6.88005C6.80444 6.94847 6.80444 7.05153 6.82134 7.11995C6.84338 7.20913 6.8857 7.27024 6.97034 7.39246C8.05424 8.95767 9.89402 10 12 10C14.106 10 15.9458 8.95766 17.0297 7.39246C17.1143 7.27024 17.1566 7.20913 17.1787 7.11995C17.1956 7.05153 17.1956 6.94847 17.1787 6.88004C17.1566 6.79086 17.1143 6.72975 17.0297 6.60753C15.9458 5.04233 14.106 4 12 4C9.89402 4 8.05424 5.04233 6.97034 6.60754ZM19.3733 7.29651C19.4182 7.19726 19.4406 7.14764 19.4514 7.08452C19.4601 7.03407 19.4601 6.96593 19.4514 6.91548C19.4406 6.85236 19.4182 6.80274 19.3733 6.70349C18.1212 3.93428 15.2928 2 12 2C8.70721 2 5.87877 3.93428 4.62672 6.70349C4.58185 6.80274 4.55941 6.85236 4.54859 6.91548C4.53993 6.96593 4.53993 7.03407 4.54859 7.08452C4.55941 7.14764 4.58185 7.19726 4.62672 7.29651C5.87877 10.0657 8.70721 12 12 12C15.2928 12 18.1212 10.0657 19.3733 7.29651Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 9C10.896 9 10 8.104 10 7C10 5.896 10.896 5 12 5C13.104 5 14 5.896 14 7C14 8.104 13.104 9 12 9Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M9.6645 14C9.13165 14 8.86523 14 8.72839 14.1092C8.60938 14.2042 8.54015 14.3483 8.54031 14.5005C8.5405 14.6756 8.70694 14.8837 9.03981 15.2998L12 19L14.9602 15.2998C15.2931 14.8837 15.4595 14.6756 15.4597 14.5005C15.4599 14.3483 15.3906 14.2042 15.2716 14.1092C15.1348 14 14.8684 14 14.3355 14H9.6645Z" style="fill: var(--element-active-color)"/>
<path d="M2 22H5V20H2V22Z" style="fill: var(--element-active-color)"/>
<path d="M7 22H11V20H7V22Z" style="fill: var(--element-active-color)"/>
<path d="M13 22H17V20H13V22Z" style="fill: var(--element-active-color)"/>
<path d="M19 22H22V20H19V22Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.97034 6.60754C6.8857 6.72976 6.84338 6.79087 6.82134 6.88005C6.80444 6.94847 6.80444 7.05153 6.82134 7.11995C6.84338 7.20913 6.8857 7.27024 6.97034 7.39246C8.05424 8.95767 9.89402 10 12 10C14.106 10 15.9458 8.95766 17.0297 7.39246C17.1143 7.27024 17.1566 7.20913 17.1787 7.11995C17.1956 7.05153 17.1956 6.94847 17.1787 6.88004C17.1566 6.79086 17.1143 6.72975 17.0297 6.60753C15.9458 5.04233 14.106 4 12 4C9.89402 4 8.05424 5.04233 6.97034 6.60754ZM19.3733 7.29651C19.4182 7.19726 19.4406 7.14764 19.4514 7.08452C19.4601 7.03407 19.4601 6.96593 19.4514 6.91548C19.4406 6.85236 19.4182 6.80274 19.3733 6.70349C18.1212 3.93428 15.2928 2 12 2C8.70721 2 5.87877 3.93428 4.62672 6.70349C4.58185 6.80274 4.55941 6.85236 4.54859 6.91548C4.53993 6.96593 4.53993 7.03407 4.54859 7.08452C4.55941 7.14764 4.58185 7.19726 4.62672 7.29651C5.87877 10.0657 8.70721 12 12 12C15.2928 12 18.1212 10.0657 19.3733 7.29651Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 9C10.896 9 10 8.104 10 7C10 5.896 10.896 5 12 5C13.104 5 14 5.896 14 7C14 8.104 13.104 9 12 9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Kr.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;$a([s({type:Boolean})],Kr.prototype,"useCssColor",2);Kr=$a([h("obi-monitoring-route")],Kr);var d2=Object.defineProperty,p2=Object.getOwnPropertyDescriptor,Va=(t,e,i,o)=>{for(var r=o>1?void 0:o?p2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&d2(e,i,r),r},eo=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="10" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" fill="currentColor"/>
<path d="M7.03865 16.2869L11.4846 5.33535C11.6661 4.88821 12.3339 4.88822 12.5154 5.33536L16.9613 16.2869C17.1482 16.7473 16.6205 17.1744 16.1697 16.9277L12.2763 14.7964C12.1053 14.7029 11.8947 14.7029 11.7237 14.7964L7.8303 16.9277C7.37952 17.1744 6.85176 16.7473 7.03865 16.2869Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="10" style="fill: var(--element-active-inverted-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" style="fill: var(--element-active-color)"/>
<path d="M7.03865 16.2869L11.4846 5.33535C11.6661 4.88821 12.3339 4.88822 12.5154 5.33536L16.9613 16.2869C17.1482 16.7473 16.6205 17.1744 16.1697 16.9277L12.2763 14.7964C12.1053 14.7029 11.8947 14.7029 11.7237 14.7964L7.8303 16.9277C7.37952 17.1744 6.85176 16.7473 7.03865 16.2869Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};eo.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Va([s({type:Boolean})],eo.prototype,"useCssColor",2);eo=Va([h("obi-own-ship-alternative-filled")],eo);var h2=Object.defineProperty,u2=Object.getOwnPropertyDescriptor,_a=(t,e,i,o)=>{for(var r=o>1?void 0:o?u2(e,i):e,a=t.length-1,n;a>=0;a--)(n=t[a])&&(r=(o?n(e,i,r):n(r))||r);return o&&r&&h2(e,i,r),r},to=class extends d{constructor(){super(...arguments),this.useCssColor=!1,this.icon=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11Z" fill="currentColor"/>
<path d="M10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5Z" fill="currentColor"/>
<path d="M11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 18H5.75C5.33579 18 5 18.3358 5 18.75C5 19.1642 5.33579 19.5 5.75 19.5H7V22H17V19.5H18.25C18.6642 19.5 19 19.1642 19 18.75C19 18.3358 18.6642 18 18.25 18H17V8.13589C17 4.52847 15.1638 2.32578 12.4415 1.18502L12 1L11.5585 1.18502C8.8362 2.32578 7 4.52847 7 8.13589V18ZM8.5 8.13589C8.5 6.59736 8.88734 5.45436 9.48804 4.5945C10.0693 3.76246 10.9128 3.10684 12 2.62785C13.0872 3.10684 13.9307 3.76246 14.512 4.5945C15.1127 5.45436 15.5 6.59736 15.5 8.13589V18H14C14 17.1716 13.3284 16.5 12.5 16.5H11.5C10.6716 16.5 10 17.1716 10 18H8.5V8.13589ZM8.5 20.5V19.5H15.5V20.5H8.5Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M9.48804 4.5945C8.88734 5.45436 8.5 6.59736 8.5 8.13589V18H10C10 17.1716 10.6716 16.5 11.5 16.5H12.5C13.3284 16.5 14 17.1716 14 18H15.5V8.13589C15.5 6.59736 15.1127 5.45436 14.512 4.5945C13.9307 3.76246 13.0872 3.10684 12 2.62785C10.9128 3.10684 10.0693 3.76246 9.48804 4.5945ZM11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11ZM10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5ZM11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" fill="currentColor"/>
<path d="M8.5 19.5V20.5H15.5V19.5H8.5Z" fill="currentColor"/>
<path d="M11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11Z" fill="currentColor"/>
<path d="M10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5Z" fill="currentColor"/>
<path d="M11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 18H5.75C5.33579 18 5 18.3358 5 18.75C5 19.1642 5.33579 19.5 5.75 19.5H7V22H17V19.5H18.25C18.6642 19.5 19 19.1642 19 18.75C19 18.3358 18.6642 18 18.25 18H17V8.13589C17 4.52847 15.1638 2.32578 12.4415 1.18502L12 1L11.5585 1.18502C8.8362 2.32578 7 4.52847 7 8.13589V18ZM8.5 8.13589C8.5 6.59736 8.88734 5.45436 9.48804 4.5945C10.0693 3.76246 10.9128 3.10684 12 2.62785C13.0872 3.10684 13.9307 3.76246 14.512 4.5945C15.1127 5.45436 15.5 6.59736 15.5 8.13589V18H14C14 17.1716 13.3284 16.5 12.5 16.5H11.5C10.6716 16.5 10 17.1716 10 18H8.5V8.13589ZM8.5 20.5V19.5H15.5V20.5H8.5Z" fill="currentColor"/>
</svg>
`,this.iconCss=l`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11Z" style="fill: var(--element-active-inverted-color)"/>
<path d="M10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5Z" style="fill: var(--element-active-inverted-color)"/>
<path d="M11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" style="fill: var(--element-active-inverted-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 18H5.75C5.33579 18 5 18.3358 5 18.75C5 19.1642 5.33579 19.5 5.75 19.5H7V22H17V19.5H18.25C18.6642 19.5 19 19.1642 19 18.75C19 18.3358 18.6642 18 18.25 18H17V8.13589C17 4.52847 15.1638 2.32578 12.4415 1.18502L12 1L11.5585 1.18502C8.8362 2.32578 7 4.52847 7 8.13589V18ZM8.5 8.13589C8.5 6.59736 8.88734 5.45436 9.48804 4.5945C10.0693 3.76246 10.9128 3.10684 12 2.62785C13.0872 3.10684 13.9307 3.76246 14.512 4.5945C15.1127 5.45436 15.5 6.59736 15.5 8.13589V18H14C14 17.1716 13.3284 16.5 12.5 16.5H11.5C10.6716 16.5 10 17.1716 10 18H8.5V8.13589ZM8.5 20.5V19.5H15.5V20.5H8.5Z" style="fill: var(--element-active-inverted-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M9.48804 4.5945C8.88734 5.45436 8.5 6.59736 8.5 8.13589V18H10C10 17.1716 10.6716 16.5 11.5 16.5H12.5C13.3284 16.5 14 17.1716 14 18H15.5V8.13589C15.5 6.59736 15.1127 5.45436 14.512 4.5945C13.9307 3.76246 13.0872 3.10684 12 2.62785C10.9128 3.10684 10.0693 3.76246 9.48804 4.5945ZM11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11ZM10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5ZM11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" style="fill: var(--element-active-inverted-color)"/>
<path d="M8.5 19.5V20.5H15.5V19.5H8.5Z" style="fill: var(--element-active-inverted-color)"/>
<path d="M11 13C10.4477 13 10 13.4477 10 14C10 14.5523 10.4477 15 11 15H13C13.5523 15 14 14.5523 14 14C14 13.4477 13.5523 13 13 13H11Z" style="fill: var(--element-active-color)"/>
<path d="M10 10.5C10 9.94771 10.4477 9.5 11 9.5H13C13.5523 9.5 14 9.94771 14 10.5C14 11.0523 13.5523 11.5 13 11.5H11C10.4477 11.5 10 11.0523 10 10.5Z" style="fill: var(--element-active-color)"/>
<path d="M11 6C10.4477 6 10 6.44772 10 7C10 7.55228 10.4477 8 11 8H13C13.5523 8 14 7.55228 14 7C14 6.44772 13.5523 6 13 6H11Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 18H5.75C5.33579 18 5 18.3358 5 18.75C5 19.1642 5.33579 19.5 5.75 19.5H7V22H17V19.5H18.25C18.6642 19.5 19 19.1642 19 18.75C19 18.3358 18.6642 18 18.25 18H17V8.13589C17 4.52847 15.1638 2.32578 12.4415 1.18502L12 1L11.5585 1.18502C8.8362 2.32578 7 4.52847 7 8.13589V18ZM8.5 8.13589C8.5 6.59736 8.88734 5.45436 9.48804 4.5945C10.0693 3.76246 10.9128 3.10684 12 2.62785C13.0872 3.10684 13.9307 3.76246 14.512 4.5945C15.1127 5.45436 15.5 6.59736 15.5 8.13589V18H14C14 17.1716 13.3284 16.5 12.5 16.5H11.5C10.6716 16.5 10 17.1716 10 18H8.5V8.13589ZM8.5 20.5V19.5H15.5V20.5H8.5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return c`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};to.styles=p`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;_a([s({type:Boolean})],to.prototype,"useCssColor",2);to=_a([h("obi-vessel-type-cargo-filled")],to);
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
@lit/reactive-element/decorators/custom-element.js:
@lit/reactive-element/decorators/property.js:
@lit/reactive-element/decorators/state.js:
@lit/reactive-element/decorators/event-options.js:
@lit/reactive-element/decorators/base.js:
@lit/reactive-element/decorators/query.js:
@lit/reactive-element/decorators/query-all.js:
@lit/reactive-element/decorators/query-async.js:
@lit/reactive-element/decorators/query-assigned-nodes.js:
lit-html/directive.js:
lit-html/async-directive.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/decorators/query-assigned-elements.js:
@lit/localize/internal/locale-status-event.js:
@lit/localize/internal/str-tag.js:
@lit/localize/internal/types.js:
@lit/localize/internal/default-msg.js:
@lit/localize/internal/localized-controller.js:
@lit/localize/internal/localized-decorator.js:
@lit/localize/internal/runtime-msg.js:
@lit/localize/init/runtime.js:
@lit/localize/init/transform.js:
  (**
   * @license
   * Copyright 2021 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directives/class-map.js:
lit-html/directives/if-defined.js:
lit-html/directives/style-map.js:
  (**
   * @license
   * Copyright 2018 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/static.js:
lit-html/directive-helpers.js:
@lit/localize/internal/deferred.js:
@lit/localize/internal/id-generation.js:
@lit/localize/lit-localize.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/localize/internal/fnv1a64.js:
  (**
   * @license
   * Copyright 2014 Travis Webb
   * SPDX-License-Identifier: MIT
   *)
*/
