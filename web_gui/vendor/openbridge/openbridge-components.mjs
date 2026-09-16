var An=globalThis;var Zn=An.ShadowRoot&&(void 0===An.ShadyCSS||An.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype;var r1=Symbol();var Gc=new WeakMap;var Oa=class{constructor(t,i,o){if(this._$cssResult$=true,o!==r1)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=i}get styleSheet(){let t=this.o;const i=this.t;if(Zn&&void 0===t){const o=void 0!==i&&1===i.length;o&&(t=Gc.get(i)),void 0===t&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),o&&Gc.set(i,t))}return t}toString(){return this.cssText}};var Q=e=>new Oa("string"==typeof e?e:e+"",void 0,r1);var L=(e,...t)=>{const i=1===e.length?e[0]:t.reduce((o,r,a)=>o+(n=>{if(true===n._$cssResult$)return n.cssText;if("number"==typeof n)return n;throw Error("Value passed to 'css' function must be a 'css' function result: "+n+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(r)+e[a+1],e[0]);return new Oa(i,e,r1)};var qc=(e,t)=>{if(Zn)e.adoptedStyleSheets=t.map(i=>i instanceof CSSStyleSheet?i:i.styleSheet);else for(const i of t){const o=document.createElement("style"),r=An.litNonce;void 0!==r&&o.setAttribute("nonce",r),o.textContent=i.cssText,e.appendChild(o)}};var o1=Zn?e=>e:e=>e instanceof CSSStyleSheet?(t=>{let i="";for(const o of t.cssRules)i+=o.cssText;return Q(i)})(e):e;var{is:Yh,defineProperty:Qh,getOwnPropertyDescriptor:Kh,getOwnPropertyNames:Xh,getOwnPropertySymbols:Jh,getPrototypeOf:e4}=Object;var Tn=globalThis;var Yc=Tn.trustedTypes;var t4=Yc?Yc.emptyScript:"";var r4=Tn.reactiveElementPolyfillSupport;var Da=(e,t)=>e;var Ea={toAttribute(e,t){switch(t){case Boolean:e=e?t4:null;break;case Object:case Array:e=null==e?e:JSON.stringify(e)}return e},fromAttribute(e,t){let i=e;switch(t){case Boolean:i=null!==e;break;case Number:i=null===e?null:Number(e);break;case Object:case Array:try{i=JSON.parse(e)}catch(o){i=null}}return i}};var Pn=(e,t)=>!Yh(e,t);var Qc={attribute:true,type:String,converter:Ea,reflect:false,useDefault:false,hasChanged:Pn};Symbol.metadata??=Symbol("metadata"),Tn.litPropertyMetadata??=new WeakMap;var bo=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,i=Qc){if(i.state&&(i.attribute=false),this._$Ei(),this.prototype.hasOwnProperty(t)&&((i=Object.create(i)).wrapped=true),this.elementProperties.set(t,i),!i.noAccessor){const o=Symbol(),r=this.getPropertyDescriptor(t,o,i);void 0!==r&&Qh(this.prototype,t,r)}}static getPropertyDescriptor(t,i,o){const{get:r,set:a}=Kh(this.prototype,t)??{get(){return this[i]},set(n){this[i]=n}};return{get:r,set(n){const p=r?.call(this);a?.call(this,n),this.requestUpdate(t,p,o)},configurable:true,enumerable:true}}static getPropertyOptions(t){return this.elementProperties.get(t)??Qc}static _$Ei(){if(this.hasOwnProperty(Da("elementProperties")))return;const t=e4(this);t.finalize(),void 0!==t.l&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(Da("finalized")))return;if(this.finalized=true,this._$Ei(),this.hasOwnProperty(Da("properties"))){const i=this.properties,o=[...Xh(i),...Jh(i)];for(const r of o)this.createProperty(r,i[r])}const t=this[Symbol.metadata];if(null!==t){const i=litPropertyMetadata.get(t);if(void 0!==i)for(const[o,r]of i)this.elementProperties.set(o,r)}this._$Eh=new Map;for(const[i,o]of this.elementProperties){const r=this._$Eu(i,o);void 0!==r&&this._$Eh.set(r,i)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){const i=[];if(Array.isArray(t)){const o=new Set(t.flat(1/0).reverse());for(const r of o)i.unshift(o1(r))}else void 0!==t&&i.push(o1(t));return i}static _$Eu(t,i){const o=i.attribute;return false===o?void 0:"string"==typeof o?o:"string"==typeof t?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=false,this.hasUpdated=false,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),void 0!==this.renderRoot&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){const t=new Map,i=this.constructor.elementProperties;for(const o of i.keys())this.hasOwnProperty(o)&&(t.set(o,this[o]),delete this[o]);t.size>0&&(this._$Ep=t)}createRenderRoot(){const t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return qc(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(true),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,i,o){this._$AK(t,o)}_$ET(t,i){const o=this.constructor.elementProperties.get(t),r=this.constructor._$Eu(t,o);if(void 0!==r&&true===o.reflect){const a=(void 0!==o.converter?.toAttribute?o.converter:Ea).toAttribute(i,o.type);this._$Em=t,null==a?this.removeAttribute(r):this.setAttribute(r,a),this._$Em=null}}_$AK(t,i){const o=this.constructor,r=o._$Eh.get(t);if(void 0!==r&&this._$Em!==r){const a=o.getPropertyOptions(r),n="function"==typeof a.converter?{fromAttribute:a.converter}:void 0!==a.converter?.fromAttribute?a.converter:Ea;this._$Em=r;const p=n.fromAttribute(i,a.type);this[r]=p??this._$Ej?.get(r)??p,this._$Em=null}}requestUpdate(t,i,o,r=false,a){if(void 0!==t){const n=this.constructor;if(false===r&&(a=this[t]),o??=n.getPropertyOptions(t),!((o.hasChanged??Pn)(a,i)||o.useDefault&&o.reflect&&a===this._$Ej?.get(t)&&!this.hasAttribute(n._$Eu(t,o))))return;this.C(t,i,o)}false===this.isUpdatePending&&(this._$ES=this._$EP())}C(t,i,{useDefault:o,reflect:r,wrapped:a},n){o&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,n??i??this[t]),true!==a||void 0!==n)||(this._$AL.has(t)||(this.hasUpdated||o||(i=void 0),this._$AL.set(t,i)),true===r&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=true;try{await this._$ES}catch(i){Promise.reject(i)}const t=this.scheduleUpdate();return null!=t&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(const[r,a]of this._$Ep)this[r]=a;this._$Ep=void 0}const o=this.constructor.elementProperties;if(o.size>0)for(const[r,a]of o){const{wrapped:n}=a,p=this[r];true!==n||this._$AL.has(r)||void 0===p||this.C(r,void 0,a,p)}}let t=false;const i=this._$AL;try{t=this.shouldUpdate(i),t?(this.willUpdate(i),this._$EO?.forEach(o=>o.hostUpdate?.()),this.update(i)):this._$EM()}catch(o){throw t=false,this._$EM(),o}t&&this._$AE(i)}willUpdate(t){}_$AE(t){this._$EO?.forEach(i=>i.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=true,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=false}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return true}update(t){this._$Eq&&=this._$Eq.forEach(i=>this._$ET(i,this[i])),this._$EM()}updated(t){}firstUpdated(t){}};bo.elementStyles=[],bo.shadowRootOptions={mode:"open"},bo[Da("elementProperties")]=new Map,bo[Da("finalized")]=new Map,r4?.({ReactiveElement:bo}),(Tn.reactiveElementVersions??=[]).push("2.1.2");var a1=globalThis;var Kc=e=>e;var zn=a1.trustedTypes;var Xc=zn?zn.createPolicy("lit-html",{createHTML:e=>e}):void 0;var n1="$lit$";var yo=`lit$${Math.random().toFixed(9).slice(2)}$`;var l1="?"+yo;var o4=`<${l1}>`;var ui=document;var Ia=()=>ui.createComment("");var Na=e=>null===e||"object"!=typeof e&&"function"!=typeof e;var s1=Array.isArray;var id=e=>s1(e)||"function"==typeof e?.[Symbol.iterator];var i1="[ 	\n\f\r]";var Ra=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g;var Jc=/-->/g;var ed=/>/g;var pi=RegExp(`>|${i1}(?:([^\\s"'>=/]+)(${i1}*=${i1}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g");var td=/'/g;var rd=/"/g;var ad=/^(?:script|style|textarea|title)$/i;var c1=e=>(t,...i)=>({_$litType$:e,strings:t,values:i});var h=c1(1);var c=c1(2);var nd=c1(3);var ar=Symbol.for("lit-noChange");var w=Symbol.for("lit-nothing");var od=new WeakMap;var hi=ui.createTreeWalker(ui,129);function ld(e,t){if(!s1(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return void 0!==Xc?Xc.createHTML(t):t}var sd=(e,t)=>{const i=e.length-1,o=[];let r,a=2===t?"<svg>":3===t?"<math>":"",n=Ra;for(let p=0;p<i;p++){const d=e[p];let f,g,m=-1,u=0;for(;u<d.length&&(n.lastIndex=u,g=n.exec(d),null!==g);)u=n.lastIndex,n===Ra?"!--"===g[1]?n=Jc:void 0!==g[1]?n=ed:void 0!==g[2]?(ad.test(g[2])&&(r=RegExp("</"+g[2],"g")),n=pi):void 0!==g[3]&&(n=pi):n===pi?">"===g[0]?(n=r??Ra,m=-1):void 0===g[1]?m=-2:(m=n.lastIndex-g[2].length,f=g[1],n=void 0===g[3]?pi:'"'===g[3]?rd:td):n===rd||n===td?n=pi:n===Jc||n===ed?n=Ra:(n=pi,r=void 0);const M=n===pi&&e[p+1].startsWith("/>")?" ":"";a+=n===Ra?d+o4:m>=0?(o.push(f),d.slice(0,m)+n1+d.slice(m)+yo+M):d+yo+(-2===m?p:M)}return[ld(e,a+(e[i]||"<?>")+(2===t?"</svg>":3===t?"</math>":"")),o]};var ja=class e{constructor({strings:t,_$litType$:i},o){let r;this.parts=[];let a=0,n=0;const p=t.length-1,d=this.parts,[f,g]=sd(t,i);if(this.el=e.createElement(f,o),hi.currentNode=this.el.content,2===i||3===i){const m=this.el.content.firstChild;m.replaceWith(...m.childNodes)}for(;null!==(r=hi.nextNode())&&d.length<p;){if(1===r.nodeType){if(r.hasAttributes())for(const m of r.getAttributeNames())if(m.endsWith(n1)){const u=g[n++],M=r.getAttribute(m).split(yo),C=/([.?@])?(.*)/.exec(u);d.push({type:1,index:a,name:C[2],strings:M,ctor:"."===C[1]?On:"?"===C[1]?Dn:"@"===C[1]?En:vi}),r.removeAttribute(m)}else m.startsWith(yo)&&(d.push({type:6,index:a}),r.removeAttribute(m));if(ad.test(r.tagName)){const m=r.textContent.split(yo),u=m.length-1;if(u>0){r.textContent=zn?zn.emptyScript:"";for(let M=0;M<u;M++)r.append(m[M],Ia()),hi.nextNode(),d.push({type:2,index:++a});r.append(m[u],Ia())}}}else if(8===r.nodeType)if(r.data===l1)d.push({type:2,index:a});else{let m=-1;for(;-1!==(m=r.data.indexOf(yo,m+1));)d.push({type:7,index:a}),m+=yo.length-1}a++}}static createElement(t,i){const o=ui.createElement("template");return o.innerHTML=t,o}};function fi(e,t,i=e,o){if(t===ar)return t;let r=void 0!==o?i._$Co?.[o]:i._$Cl;const a=Na(t)?void 0:t._$litDirective$;return r?.constructor!==a&&(r?._$AO?.(false),void 0===a?r=void 0:(r=new a(e),r._$AT(e,i,o)),void 0!==o?(i._$Co??=[])[o]=r:i._$Cl=r),void 0!==r&&(t=fi(e,r._$AS(e,t.values),r,o)),t}var Bn=class{constructor(t,i){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=i}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){const{el:{content:i},parts:o}=this._$AD,r=(t?.creationScope??ui).importNode(i,true);hi.currentNode=r;let a=hi.nextNode(),n=0,p=0,d=o[0];for(;void 0!==d;){if(n===d.index){let f;2===d.type?f=new oa(a,a.nextSibling,this,t):1===d.type?f=new d.ctor(a,d.name,d.strings,this,t):6===d.type&&(f=new Rn(a,this,t)),this._$AV.push(f),d=o[++p]}n!==d?.index&&(a=hi.nextNode(),n++)}return hi.currentNode=ui,r}p(t){let i=0;for(const o of this._$AV)void 0!==o&&(void 0!==o.strings?(o._$AI(t,o,i),i+=o.strings.length-2):o._$AI(t[i])),i++}};var oa=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,i,o,r){this.type=2,this._$AH=w,this._$AN=void 0,this._$AA=t,this._$AB=i,this._$AM=o,this.options=r,this._$Cv=r?.isConnected??true}get parentNode(){let t=this._$AA.parentNode;const i=this._$AM;return void 0!==i&&11===t?.nodeType&&(t=i.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,i=this){t=fi(this,t,i),Na(t)?t===w||null==t||""===t?(this._$AH!==w&&this._$AR(),this._$AH=w):t!==this._$AH&&t!==ar&&this._(t):void 0!==t._$litType$?this.$(t):void 0!==t.nodeType?this.T(t):id(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==w&&Na(this._$AH)?this._$AA.nextSibling.data=t:this.T(ui.createTextNode(t)),this._$AH=t}$(t){const{values:i,_$litType$:o}=t,r="number"==typeof o?this._$AC(t):(void 0===o.el&&(o.el=ja.createElement(ld(o.h,o.h[0]),this.options)),o);if(this._$AH?._$AD===r)this._$AH.p(i);else{const a=new Bn(r,this),n=a.u(this.options);a.p(i),this.T(n),this._$AH=a}}_$AC(t){let i=od.get(t.strings);return void 0===i&&od.set(t.strings,i=new ja(t)),i}k(t){s1(this._$AH)||(this._$AH=[],this._$AR());const i=this._$AH;let o,r=0;for(const a of t)r===i.length?i.push(o=new e(this.O(Ia()),this.O(Ia()),this,this.options)):o=i[r],o._$AI(a),r++;r<i.length&&(this._$AR(o&&o._$AB.nextSibling,r),i.length=r)}_$AR(t=this._$AA.nextSibling,i){for(this._$AP?.(false,true,i);t!==this._$AB;){const o=Kc(t).nextSibling;Kc(t).remove(),t=o}}setConnected(t){void 0===this._$AM&&(this._$Cv=t,this._$AP?.(t))}};var vi=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,i,o,r,a){this.type=1,this._$AH=w,this._$AN=void 0,this.element=t,this.name=i,this._$AM=r,this.options=a,o.length>2||""!==o[0]||""!==o[1]?(this._$AH=Array(o.length-1).fill(new String),this.strings=o):this._$AH=w}_$AI(t,i=this,o,r){const a=this.strings;let n=false;if(void 0===a)t=fi(this,t,i,0),n=!Na(t)||t!==this._$AH&&t!==ar,n&&(this._$AH=t);else{const p=t;let d,f;for(t=a[0],d=0;d<a.length-1;d++)f=fi(this,p[o+d],i,d),f===ar&&(f=this._$AH[d]),n||=!Na(f)||f!==this._$AH[d],f===w?t=w:t!==w&&(t+=(f??"")+a[d+1]),this._$AH[d]=f}n&&!r&&this.j(t)}j(t){t===w?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}};var On=class extends vi{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===w?void 0:t}};var Dn=class extends vi{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==w)}};var En=class extends vi{constructor(t,i,o,r,a){super(t,i,o,r,a),this.type=5}_$AI(t,i=this){if((t=fi(this,t,i,0)??w)===ar)return;const o=this._$AH,r=t===w&&o!==w||t.capture!==o.capture||t.once!==o.once||t.passive!==o.passive,a=t!==w&&(o===w||r);r&&this.element.removeEventListener(this.name,this,o),a&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){"function"==typeof this._$AH?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}};var Rn=class{constructor(t,i,o){this.element=t,this.type=6,this._$AN=void 0,this._$AM=i,this.options=o}get _$AU(){return this._$AM._$AU}_$AI(t){fi(this,t)}};var cd={M:n1,P:yo,A:l1,C:1,L:sd,R:Bn,D:id,V:fi,I:oa,H:vi,N:Dn,U:En,B:On,F:Rn};var i4=a1.litHtmlPolyfillSupport;i4?.(ja,oa),(a1.litHtmlVersions??=[]).push("3.3.3");var dd=(e,t,i)=>{const o=i?.renderBefore??t;let r=o._$litPart$;if(void 0===r){const a=i?.renderBefore??null;o._$litPart$=r=new oa(t.insertBefore(Ia(),a),a,void 0,i??{})}return r._$AI(e),r};var d1=globalThis;var k=class extends bo{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){const t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){const i=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=dd(i,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(true)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(false)}render(){return ar}};k._$litElement$=true,k["finalized"]=true,d1.litElementHydrateSupport?.({LitElement:k});var a4=d1.litElementPolyfillSupport;a4?.({LitElement:k});(d1.litElementVersions??=[]).push("4.2.2");var pd=false;var n4={attribute:true,type:String,converter:Ea,reflect:false,hasChanged:Pn};var l4=(e=n4,t,i)=>{const{kind:o,metadata:r}=i;let a=globalThis.litPropertyMetadata.get(r);if(void 0===a&&globalThis.litPropertyMetadata.set(r,a=new Map),"setter"===o&&((e=Object.create(e)).wrapped=true),a.set(i.name,e),"accessor"===o){const{name:n}=i;return{set(p){const d=t.get.call(this);t.set.call(this,p),this.requestUpdate(n,d,e,true,p)},init(p){return void 0!==p&&this.C(n,void 0,e,p),p}}}if("setter"===o){const{name:n}=i;return function(p){const d=this[n];t.call(this,p),this.requestUpdate(n,d,e,true,p)}}throw Error("Unsupported decorator location: "+o)};function l(e){return(t,i)=>"object"==typeof i?l4(e,t,i):((o,r,a)=>{const n=r.hasOwnProperty(a);return r.constructor.createProperty(a,o),n?Object.getOwnPropertyDescriptor(r,a):void 0})(e,t,i)}function Ve(e){return l({...e,state:true,attribute:false})}var Oo=(e,t,i)=>(i.configurable=true,i.enumerable=true,Reflect.decorate&&"object"!=typeof t&&Object.defineProperty(e,t,i),i);function Do(e,t){return(i,o,r)=>{const a=n=>n.renderRoot?.querySelector(e)??null;if(t){const{get:n,set:p}="object"==typeof o?i:r??(()=>{const d=Symbol();return{get(){return this[d]},set(f){this[d]=f}}})();return Oo(i,o,{get(){let d=n.call(this);return void 0===d&&(d=a(this),(null!==d||this.hasUpdated)&&p.call(this,d)),d}})}return Oo(i,o,{get(){return a(this)}})}}function hd(e){return(t,i)=>{const{slot:o,selector:r}=e??{},a="slot"+(o?`[name=${o}]`:":not([name])");return Oo(t,i,{get(){const n=this.renderRoot?.querySelector(a),p=n?.assignedElements(e)??[];return void 0===r?p:p.filter(d=>d.matches(r))}})}}var Eo={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6};var wo=e=>(...t)=>({_$litDirective$:e,values:t});var to=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,i,o){this._$Ct=t,this._$AM=i,this._$Ci=o}_$AS(t,i){return this.update(t,i)}update(t,i){return this.render(...i)}};var J=wo(class extends to{constructor(e){if(super(e),e.type!==Eo.ATTRIBUTE||"class"!==e.name||e.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(e){return" "+Object.keys(e).filter(t=>e[t]).join(" ")+" "}update(e,[t]){if(void 0===this.st){this.st=new Set,void 0!==e.strings&&(this.nt=new Set(e.strings.join(" ").split(/\s/).filter(o=>""!==o)));for(const o in t)t[o]&&!this.nt?.has(o)&&this.st.add(o);return this.render(t)}const i=e.element.classList;for(const o of this.st)o in t||(i.remove(o),this.st.delete(o));for(const o in t){const r=!!t[o];r===this.st.has(o)||this.nt?.has(o)||(r?(i.add(o),this.st.add(o)):(i.remove(o),this.st.delete(o)))}return ar}});var ud=L`
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
`;var fd=L`
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
`;var x=e=>(t,i)=>{if(i!==void 0){i.addInitializer(()=>{if(customElements.get(e)){if(true){console.error(`Element ${e} is already registered`)}return}customElements.define(e,t)})}else{if(customElements.get(e)){if(true){console.error(`Element ${e} is already registered`)}return}customElements.define(e,t)}};var s4=Object.defineProperty;var c4=Object.getOwnPropertyDescriptor;var ro=(e,t,i,o)=>{var r=o>1?void 0:o?c4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)s4(t,i,r);return r};var Cr=class extends k{constructor(){super(...arguments);this.variant="normal";this.activated=false;this.cornerLeft=false;this.cornerRight=false;this.activeColor=false;this.wide=false;this.disabled=false;this.progress=void 0;this.hasLabel=false}get progressSpinner(){if(this.progress===void 0){return w}if(this.progress===100){return h`<div class="progress-spinner">
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
      </div>`}const e=this.progress*.95*3.6*Math.PI/180;const t=20+18*Math.sin(e);const i=20-18*Math.cos(e);const o=e>Math.PI?1:0;return h`<div class="progress-spinner">
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
          d="M18 2 A18 18 0 ${o} 1 ${t} ${i}"
          stroke="var(--instrument-enhanced-secondary-color)"
          stroke-width="4"
          stroke-linecap="round"
        />
      </svg>
    </div>`}render(){return h`
      <button
        class=${J({wrapper:true,["variant-"+this.variant]:true,activated:this.activated,"corner-left":this.cornerLeft,"corner-right":this.cornerRight,"active-color":this.activeColor,"has-label":this.hasLabel,wide:this.wide,progress:this.progress!==void 0})}
        ?disabled=${this.disabled}
        part="wrapper"
      >
        ${this.progress!==void 0?this.progressSpinner:w}
        <div class="visible-wrapper" part="visible-wrapper">
          <div class="icon" part="icon">
            <slot></slot>
          </div>
        </div>
        ${this.hasLabel?h`<div class="label" part="label">
              <slot name="label"></slot>
            </div>`:w}
      </button>
    `}};Cr.styles=Q(fd);ro([l({type:String})],Cr.prototype,"variant",2);ro([l({type:Boolean})],Cr.prototype,"activated",2);ro([l({type:Boolean})],Cr.prototype,"cornerLeft",2);ro([l({type:Boolean})],Cr.prototype,"cornerRight",2);ro([l({type:Boolean})],Cr.prototype,"activeColor",2);ro([l({type:Boolean})],Cr.prototype,"wide",2);ro([l({type:Boolean})],Cr.prototype,"disabled",2);ro([l({type:Number})],Cr.prototype,"progress",2);ro([l({type:Boolean})],Cr.prototype,"hasLabel",2);Cr=ro([x("obc-icon-button")],Cr);var vd=L`
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
`;var gd=Symbol.for("");var d4=e=>{if(e?.r===gd)return e?._$litStatic$};var We=(e,...t)=>({_$litStatic$:t.reduce((i,o,r)=>i+(a=>{if(void 0!==a._$litStatic$)return a._$litStatic$;throw Error(`Value passed to 'literal' function must be a 'literal' result: ${a}. Use 'unsafeStatic' to pass non-literal values, but
            take care to ensure page security.`)})(o)+e[r+1],e[0]),r:gd});var md=new Map;var p1=e=>(t,...i)=>{const o=i.length;let r,a;const n=[],p=[];let d,f=0,g=false;for(;f<o;){for(d=t[f];f<o&&void 0!==(a=i[f],r=d4(a));)d+=r+t[++f],g=true;f!==o&&p.push(a),n.push(d),f++}if(f===o&&n.push(t[o]),g){const m=n.join("$$lit$$");void 0===(t=md.get(m))&&(n.raw=n,md.set(m,t=n)),i=p}return e(t,...i)};var ce=p1(h);var In=p1(c);var gv=p1(nd);var p4=Object.defineProperty;var h4=Object.getOwnPropertyDescriptor;var Zt=(e,t,i,o)=>{var r=o>1?void 0:o?h4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)p4(t,i,r);return r};var kt=class extends k{constructor(){super(...arguments);this.showSeconds=false;this.showDate=false;this.showTimezone=false;this.timeZoneOffsetHours=0;this.isClickable=true;this.showYear=false;this.showWeekday=false;this.locale="en-GB";this.hour12=false;this.selected=false;this.double=false;this.activated=false;this.integrationBarMode=false;this.blinkOnlyBreakpointPx=0}get timezoneString(){if(this.timeZoneOffsetHours===0){return"UTC"}return this.timeZoneOffsetHours>0?`UTC+${this.timeZoneOffsetHours}`:`UTC-${-this.timeZoneOffsetHours}`}_dateString(e){const t={month:"short",day:"numeric",weekday:this.showWeekday?"short":void 0,year:this.showYear?"numeric":void 0,timeZone:"UTC"};return e.toLocaleDateString(this.locale,t).replace(/,/g,"").replace(/\./g,"")}_ampm(e){if(this.hour12){return e<12?" AM":" PM"}return""}render(){const e=new Date(this.date);e.setUTCHours(e.getUTCHours()+this.timeZoneOffsetHours);const t=e.getUTCHours();const i=e.getUTCMinutes();const o=this.hour12?t%12:t;const r=o<10?`0${o}`:`${o}`;const a=i<10?`0${i}`:`${i}`;const n=e.getUTCSeconds();const p=n<10?`0${n}`:`${n}`;const d=this._ampm(t);const f=this._dateString(e);const g=!this.isClickable?We`div`:We`button`;const m=ce`<div class="ticks ${this.showSeconds?"":"animate"}">
      <span class="tick"></span><span class="tick"></span>
    </div>`;const u=`@media (max-width: ${this.blinkOnlyBreakpointPx}px )`;const M=ce`<div class="clock">
        ${r}${m}${a}${this.showSeconds?ce`${m}${p}`:""}${d}
      </div>

      ${this.showTimezone?ce`<div class="timezone">${this.timezoneString}</div>`:null}`;return ce`
      <style>
        ${u} {
          .wrapper {
            display: none !important;
          }
          .blink-wrapper {
            display: flex !important;
          }
        }
      </style>
      <${g} 
        class=${J({wrapper:true,"no-click":!this.isClickable,selected:this.selected,double:this.double,"integration-bar-mode":this.integrationBarMode,activated:this.activated})}>
        <div class="visible-wrapper">
          ${this.double?ce`<div class="row">${M}</div>`:M}
        ${this.showDate?ce` <div class="divider"></div>
                <div class="date">${f}</div>`:w}
        ${this.double?ce`</div>`:w}
        </div>
      </${g}>
      <div class=${J({"blink-wrapper":true,clock:true,blink:true,"integration-bar-mode":this.integrationBarMode})}>
        <div class="ticks animate"><div class="tick"></div><div class="tick"></div></div>
      </div>
    `}};kt.styles=Q(vd);Zt([l({type:String})],kt.prototype,"date",2);Zt([l({type:Boolean})],kt.prototype,"showSeconds",2);Zt([l({type:Boolean})],kt.prototype,"showDate",2);Zt([l({type:Boolean})],kt.prototype,"showTimezone",2);Zt([l({type:Number})],kt.prototype,"timeZoneOffsetHours",2);Zt([l({type:Boolean,attribute:false})],kt.prototype,"isClickable",2);Zt([l({type:Boolean})],kt.prototype,"showYear",2);Zt([l({type:Boolean})],kt.prototype,"showWeekday",2);Zt([l({type:String})],kt.prototype,"locale",2);Zt([l({type:Boolean})],kt.prototype,"hour12",2);Zt([l({type:Boolean})],kt.prototype,"selected",2);Zt([l({type:Boolean})],kt.prototype,"double",2);Zt([l({type:Boolean})],kt.prototype,"activated",2);Zt([l({type:Boolean})],kt.prototype,"integrationBarMode",2);Zt([l({type:Number})],kt.prototype,"blinkOnlyBreakpointPx",2);kt=Zt([x("obc-clock")],kt);var bd=L`
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
`;var u4=Object.getOwnPropertyDescriptor;var f4=(e,t,i,o)=>{var r=o>1?void 0:o?u4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=n(r)||r;return r};var h1=class extends k{render(){return h``}};h1.styles=Q(bd);h1=f4([x("obc-divider")],h1);var yd=L`
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
`;var v4=Object.defineProperty;var m4=Object.getOwnPropertyDescriptor;var wd=(e,t,i,o)=>{var r=o>1?void 0:o?m4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)v4(t,i,r);return r};var Nn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8.59009 7.41L10.0001 6L16.0001 12L10.0001 18L8.59009 16.59L13.1701 12L8.59009 7.41Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.59009 7.41L10.0001 6L16.0001 12L10.0001 18L8.59009 16.59L13.1701 12L8.59009 7.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Nn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;wd([l({type:Boolean})],Nn.prototype,"useCssColor",2);Nn=wd([x("obi-chevron-right-google")],Nn);var g4=Object.defineProperty;var b4=Object.getOwnPropertyDescriptor;var u1=(e,t,i,o)=>{var r=o>1?void 0:o?b4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)g4(t,i,r);return r};var Fa=class extends k{constructor(){super(...arguments);this.items=[];this.iconOnly=false}render(){return h`
      <nav aria-label="Breadcrumb" class="breadcrumb">
        <ol>
          ${this.items.map((e,t)=>{const i=t===this.items.length-1;return h`
              <li>
                ${t>0?h`<span class="divider">
                      <obi-chevron-right-google class="icon">
                      </obi-chevron-right-google>
                    </span>`:w}
                ${i?h` <div class="label-wrapper active">
                      <div class="visible-wrapper">
                        ${e.icon?e.icon():w}
                        ${this.iconOnly&&!i?w:h`<span class="label">${e.label}</span>`}
                      </div>
                    </div>`:h` <button
                      role="link"
                      @click=${()=>this.handleClick(e)}
                      class="label-wrapper"
                    >
                      <div class="visible-wrapper">
                        ${e.icon?e.icon():w}
                        ${this.iconOnly&&!i?w:h`<span class="label">${e.label}</span>`}
                      </div>
                    </button>`}
              </li>
            `})}
        </ol>
      </nav>
    `}handleClick(e){this.dispatchEvent(new CustomEvent("breadcrumb-click",{detail:e}))}};Fa.styles=Q(yd);u1([l({attribute:false})],Fa.prototype,"items",2);u1([l({attribute:false})],Fa.prototype,"iconOnly",2);Fa=u1([x("obc-breadcrumb")],Fa);var y4=Object.defineProperty;var w4=Object.getOwnPropertyDescriptor;var Cd=(e,t,i,o)=>{var r=o>1?void 0:o?w4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)y4(t,i,r);return r};var jn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M3 13H21V11H3V13Z" fill="currentColor"/>
<path d="M3 18H21V16H3V18Z" fill="currentColor"/>
<path d="M3 6V8H21V6H3Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M3 13H21V11H3V13Z" style="fill: var(--element-active-color)"/>
<path d="M3 18H21V16H3V18Z" style="fill: var(--element-active-color)"/>
<path d="M3 6V8H21V6H3Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};jn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Cd([l({type:Boolean})],jn.prototype,"useCssColor",2);jn=Cd([x("obi-menu-iec")],jn);var C4=Object.defineProperty;var k4=Object.getOwnPropertyDescriptor;var kd=(e,t,i,o)=>{var r=o>1?void 0:o?k4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)C4(t,i,r);return r};var Fn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M6 19H9V13H15V19H18V10L12 5.5L6 10V19ZM4 21V9L12 3L20 9V21H13V15H11V21H4Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M6 19H9V13H15V19H18V10L12 5.5L6 10V19ZM4 21V9L12 3L20 9V21H13V15H11V21H4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Fn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;kd([l({type:Boolean})],Fn.prototype,"useCssColor",2);Fn=kd([x("obi-home")],Fn);var L4=Object.defineProperty;var x4=Object.getOwnPropertyDescriptor;var Ld=(e,t,i,o)=>{var r=o>1?void 0:o?x4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)L4(t,i,r);return r};var Un=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Un.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ld([l({type:Boolean})],Un.prototype,"useCssColor",2);Un=Ld([x("obi-close-google")],Un);var $4=Object.defineProperty;var M4=Object.getOwnPropertyDescriptor;var xd=(e,t,i,o)=>{var r=o>1?void 0:o?M4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)$4(t,i,r);return r};var Wn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7.83 11H20V13H7.83L13.41 18.59L12 20L4 12L12 4L13.42 5.41L7.83 11Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.83 11H20V13H7.83L13.41 18.59L12 20L4 12L12 4L13.42 5.41L7.83 11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Wn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;xd([l({type:Boolean})],Wn.prototype,"useCssColor",2);Wn=xd([x("obi-arrow-left-google")],Wn);var H4=Object.defineProperty;var S4=Object.getOwnPropertyDescriptor;var $d=(e,t,i,o)=>{var r=o>1?void 0:o?S4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)H4(t,i,r);return r};var Gn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 4L10.59 5.41L16.17 11H4V13H16.17L10.59 18.59L12 20L20 12L12 4Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 4L10.59 5.41L16.17 11H4V13H16.17L10.59 18.59L12 20L20 12L12 4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Gn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;$d([l({type:Boolean})],Gn.prototype,"useCssColor",2);Gn=$d([x("obi-arrow-right-google")],Gn);var _4=Object.defineProperty;var V4=Object.getOwnPropertyDescriptor;var Md=(e,t,i,o)=>{var r=o>1?void 0:o?V4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)_4(t,i,r);return r};var qn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99976 11.9999C6.99976 10.6738 7.52654 9.40202 8.46422 8.46434C9.4019 7.52666 10.6737 6.99988 11.9998 6.99988C13.3258 6.99988 14.5976 7.52666 15.5353 8.46434L16.2424 9.17145L9.17133 16.2425L8.46422 15.5354C7.52654 14.5977 6.99976 13.326 6.99976 11.9999ZM9.87843 9.87856C9.31583 10.4412 8.99976 11.2042 8.99976 11.9999C8.99976 12.4516 9.10163 12.8928 9.29265 13.2928L13.2926 9.29277C12.8927 9.10175 12.4515 8.99988 11.9998 8.99988C11.2041 8.99988 10.441 9.31595 9.87843 9.87856Z" fill="currentColor"/>
<path d="M3.51447 19.0709L6.3429 16.2425L7.75711 17.6567L4.92869 20.4852L3.51447 19.0709Z" fill="currentColor"/>
<path d="M0.999756 10.9999H4.99976V12.9999H0.999756V10.9999Z" fill="currentColor"/>
<path d="M4.92874 3.51462L7.75717 6.34304L6.34295 7.75726L3.51453 4.92883L4.92874 3.51462Z" fill="currentColor"/>
<path d="M12.9998 0.999878V4.99988H10.9998V0.999878H12.9998Z" fill="currentColor"/>
<path d="M20.4851 4.92878L17.6567 7.75721L16.2425 6.343L19.0709 3.51457L20.4851 4.92878Z" fill="currentColor"/>
<path d="M20.1539 11C20.8 11 21.4154 11.088 22 11.253C19.5016 11.9515 17.6924 14.036 17.6924 16.5C17.6924 18.964 19.5016 21.0485 22 21.747C21.4154 21.912 20.8 22 20.1539 22C16.757 22 14 19.536 14 16.5C14 13.464 16.757 11 20.1539 11Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99976 11.9999C6.99976 10.6738 7.52654 9.40202 8.46422 8.46434C9.4019 7.52666 10.6737 6.99988 11.9998 6.99988C13.3258 6.99988 14.5976 7.52666 15.5353 8.46434L16.2424 9.17145L9.17133 16.2425L8.46422 15.5354C7.52654 14.5977 6.99976 13.326 6.99976 11.9999ZM9.87843 9.87856C9.31583 10.4412 8.99976 11.2042 8.99976 11.9999C8.99976 12.4516 9.10163 12.8928 9.29265 13.2928L13.2926 9.29277C12.8927 9.10175 12.4515 8.99988 11.9998 8.99988C11.2041 8.99988 10.441 9.31595 9.87843 9.87856Z" style="fill: var(--element-active-color)"/>
<path d="M3.51447 19.0709L6.3429 16.2425L7.75711 17.6567L4.92869 20.4852L3.51447 19.0709Z" style="fill: var(--element-active-color)"/>
<path d="M0.999756 10.9999H4.99976V12.9999H0.999756V10.9999Z" style="fill: var(--element-active-color)"/>
<path d="M4.92874 3.51462L7.75717 6.34304L6.34295 7.75726L3.51453 4.92883L4.92874 3.51462Z" style="fill: var(--element-active-color)"/>
<path d="M12.9998 0.999878V4.99988H10.9998V0.999878H12.9998Z" style="fill: var(--element-active-color)"/>
<path d="M20.4851 4.92878L17.6567 7.75721L16.2425 6.343L19.0709 3.51457L20.4851 4.92878Z" style="fill: var(--element-active-color)"/>
<path d="M20.1539 11C20.8 11 21.4154 11.088 22 11.253C19.5016 11.9515 17.6924 14.036 17.6924 16.5C17.6924 18.964 19.5016 21.0485 22 21.747C21.4154 21.912 20.8 22 20.1539 22C16.757 22 14 19.536 14 16.5C14 13.464 16.757 11 20.1539 11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};qn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Md([l({type:Boolean})],qn.prototype,"useCssColor",2);qn=Md([x("obi-palette-day-night-iec")],qn);var A4=Object.defineProperty;var Z4=Object.getOwnPropertyDescriptor;var Hd=(e,t,i,o)=>{var r=o>1?void 0:o?Z4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)A4(t,i,r);return r};var Yn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M4 8H8V4H4V8ZM10 20H14V16H10V20ZM4 20H8V16H4V20ZM4 14H8V10H4V14ZM10 14H14V10H10V14ZM16 4V8H20V4H16ZM10 8H14V4H10V8ZM16 14H20V10H16V14ZM16 20H20V16H16V20Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M4 8H8V4H4V8ZM10 20H14V16H10V20ZM4 20H8V16H4V20ZM4 14H8V10H4V14ZM10 14H14V10H10V14ZM16 4V8H20V4H16ZM10 8H14V4H10V8ZM16 14H20V10H16V14ZM16 20H20V16H16V20Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Yn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Hd([l({type:Boolean})],Yn.prototype,"useCssColor",2);Yn=Hd([x("obi-applications")],Yn);var T4=Object.defineProperty;var P4=Object.getOwnPropertyDescriptor;var Sd=(e,t,i,o)=>{var r=o>1?void 0:o?P4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)T4(t,i,r);return r};var Qn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M14 6C14 4.9 13.1 4 12 4C10.9 4 10 4.9 10 6C10 7.1 10.9 8 12 8C13.1 8 14 7.1 14 6Z" fill="currentColor"/>
<path d="M14 12C14 10.9 13.1 10 12 10C10.9 10 10 10.9 10 12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12Z" fill="currentColor"/>
<path d="M14 18C14 16.9 13.1 16 12 16C10.9 16 10 16.9 10 18C10 19.1 10.9 20 12 20C13.1 20 14 19.1 14 18Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M14 6C14 4.9 13.1 4 12 4C10.9 4 10 4.9 10 6C10 7.1 10.9 8 12 8C13.1 8 14 7.1 14 6Z" style="fill: var(--element-active-color)"/>
<path d="M14 12C14 10.9 13.1 10 12 10C10.9 10 10 10.9 10 12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12Z" style="fill: var(--element-active-color)"/>
<path d="M14 18C14 16.9 13.1 16 12 16C10.9 16 10 16.9 10 18C10 19.1 10.9 20 12 20C13.1 20 14 19.1 14 18Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Qn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Sd([l({type:Boolean})],Qn.prototype,"useCssColor",2);Qn=Sd([x("obi-more-vertical-google")],Qn);var z4=Object.defineProperty;var B4=Object.getOwnPropertyDescriptor;var _d=(e,t,i,o)=>{var r=o>1?void 0:o?B4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)z4(t,i,r);return r};var Kn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5.85 17.1C6.7 16.45 7.65 15.9375 8.7 15.5625C9.75 15.1875 10.85 15 12 15C13.15 15 14.25 15.1875 15.3 15.5625C16.35 15.9375 17.3 16.45 18.15 17.1C18.7333 16.4167 19.1875 15.6417 19.5125 14.775C19.8375 13.9083 20 12.9833 20 12C20 9.78333 19.2208 7.89583 17.6625 6.3375C16.1042 4.77917 14.2167 4 12 4C9.78333 4 7.89583 4.77917 6.3375 6.3375C4.77917 7.89583 4 9.78333 4 12C4 12.9833 4.1625 13.9083 4.4875 14.775C4.8125 15.6417 5.26667 16.4167 5.85 17.1ZM12 13C11.0167 13 10.1875 12.6625 9.5125 11.9875C8.8375 11.3125 8.5 10.4833 8.5 9.5C8.5 8.51667 8.8375 7.6875 9.5125 7.0125C10.1875 6.3375 11.0167 6 12 6C12.9833 6 13.8125 6.3375 14.4875 7.0125C15.1625 7.6875 15.5 8.51667 15.5 9.5C15.5 10.4833 15.1625 11.3125 14.4875 11.9875C13.8125 12.6625 12.9833 13 12 13ZM12 22C10.6167 22 9.31667 21.7375 8.1 21.2125C6.88333 20.6875 5.825 19.975 4.925 19.075C4.025 18.175 3.3125 17.1167 2.7875 15.9C2.2625 14.6833 2 13.3833 2 12C2 10.6167 2.2625 9.31667 2.7875 8.1C3.3125 6.88333 4.025 5.825 4.925 4.925C5.825 4.025 6.88333 3.3125 8.1 2.7875C9.31667 2.2625 10.6167 2 12 2C13.3833 2 14.6833 2.2625 15.9 2.7875C17.1167 3.3125 18.175 4.025 19.075 4.925C19.975 5.825 20.6875 6.88333 21.2125 8.1C21.7375 9.31667 22 10.6167 22 12C22 13.3833 21.7375 14.6833 21.2125 15.9C20.6875 17.1167 19.975 18.175 19.075 19.075C18.175 19.975 17.1167 20.6875 15.9 21.2125C14.6833 21.7375 13.3833 22 12 22Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5.85 17.1C6.7 16.45 7.65 15.9375 8.7 15.5625C9.75 15.1875 10.85 15 12 15C13.15 15 14.25 15.1875 15.3 15.5625C16.35 15.9375 17.3 16.45 18.15 17.1C18.7333 16.4167 19.1875 15.6417 19.5125 14.775C19.8375 13.9083 20 12.9833 20 12C20 9.78333 19.2208 7.89583 17.6625 6.3375C16.1042 4.77917 14.2167 4 12 4C9.78333 4 7.89583 4.77917 6.3375 6.3375C4.77917 7.89583 4 9.78333 4 12C4 12.9833 4.1625 13.9083 4.4875 14.775C4.8125 15.6417 5.26667 16.4167 5.85 17.1ZM12 13C11.0167 13 10.1875 12.6625 9.5125 11.9875C8.8375 11.3125 8.5 10.4833 8.5 9.5C8.5 8.51667 8.8375 7.6875 9.5125 7.0125C10.1875 6.3375 11.0167 6 12 6C12.9833 6 13.8125 6.3375 14.4875 7.0125C15.1625 7.6875 15.5 8.51667 15.5 9.5C15.5 10.4833 15.1625 11.3125 14.4875 11.9875C13.8125 12.6625 12.9833 13 12 13ZM12 22C10.6167 22 9.31667 21.7375 8.1 21.2125C6.88333 20.6875 5.825 19.975 4.925 19.075C4.025 18.175 3.3125 17.1167 2.7875 15.9C2.2625 14.6833 2 13.3833 2 12C2 10.6167 2.2625 9.31667 2.7875 8.1C3.3125 6.88333 4.025 5.825 4.925 4.925C5.825 4.025 6.88333 3.3125 8.1 2.7875C9.31667 2.2625 10.6167 2 12 2C13.3833 2 14.6833 2.2625 15.9 2.7875C17.1167 3.3125 18.175 4.025 19.075 4.925C19.975 5.825 20.6875 6.88333 21.2125 8.1C21.7375 9.31667 22 10.6167 22 12C22 13.3833 21.7375 14.6833 21.2125 15.9C20.6875 17.1167 19.975 18.175 19.075 19.075C18.175 19.975 17.1167 20.6875 15.9 21.2125C14.6833 21.7375 13.3833 22 12 22Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Kn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;_d([l({type:Boolean})],Kn.prototype,"useCssColor",2);Kn=_d([x("obi-user")],Kn);var O4=Object.defineProperty;var D4=Object.getOwnPropertyDescriptor;var Ye=(e,t,i,o)=>{var r=o>1?void 0:o?D4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)O4(t,i,r);return r};var Fe=class extends k{constructor(){super(...arguments);this.appTitle="App";this.pageName="Page";this.menuButtonIcon="menu";this.menuButtonActivated=false;this.dimmingButtonActivated=false;this.appsButtonActivated=false;this.leftMoreButtonActivated=false;this.userButtonActivated=false;this.userButtonDisabled=false;this.tall=false;this.wideMenuButton=false;this.showAppsButton=false;this.showDimmingButton=false;this.showUserButton=false;this.showClock=false;this.showDate=false;this.showAppIcon=false;this.inactive=false;this.appButtonBreakpointPx=500;this.dimmingButtonBreakpointPx=500;this.appTitleBreakpointPx=500;this.userButtonBreakpointPx=500;this.appIconBreakpointPx=500;this.settings=false;this.breadcrumbItems=[];this.leftButtonEvent=null;this.leftButtonTimeout=null;this.isLeftButtonDown=false;this.isEmergencyBrightness=false}dimmingButtonClicked(){this.dispatchEvent(new CustomEvent("dimming-button-clicked"))}appsButtonClicked(){this.dispatchEvent(new CustomEvent("apps-button-clicked"))}leftMoreButtonClicked(){this.dispatchEvent(new CustomEvent("left-more-button-clicked"))}userButtonClicked(){this.dispatchEvent(new CustomEvent("user-button-clicked"))}leftButtonDown(e){this.leftButtonEvent=e;this.isLeftButtonDown=true;this.leftButtonTimeout=setTimeout(()=>{this.leftButtonEvent=null;this.dispatchEvent(new CustomEvent("emergency-brightness-start"));this.isEmergencyBrightness=true},500)}leftButtonUp(){if(this.leftButtonEvent){this.dispatchEvent(this.leftButtonEvent);this.leftButtonEvent=null}if(this.leftButtonTimeout){clearTimeout(this.leftButtonTimeout);this.leftButtonTimeout=null}if(this.isEmergencyBrightness){this.dispatchEvent(new CustomEvent("emergency-brightness-stop"));this.isEmergencyBrightness=false}this.isLeftButtonDown=false}leftButtonLeave(){if(!this.isLeftButtonDown)return;if(this.leftButtonTimeout){clearInterval(this.leftButtonTimeout);this.leftButtonTimeout=null}if(this.isEmergencyBrightness){this.dispatchEvent(new CustomEvent("emergency-brightness-stop"));this.isEmergencyBrightness=false}this.isLeftButtonDown=false}render(){const e=[];if(this.settings){e.push(h`<div class="menu-button">
          <obc-icon-button
            variant="flat"
            @pointerdown=${()=>this.leftButtonDown(new CustomEvent("close"))}
            @pointerup=${()=>this.leftButtonUp()}
            @pointerleave=${()=>this.leftButtonLeave()}
          >
            <obi-close-google></obi-close-google>
          </obc-icon-button>
        </div>`);e.push(h`<div class="divider"></div>`);e.push(h`<obc-icon-button
          variant="flat"
          @click=${()=>this.dispatchEvent(new CustomEvent("back"))}
        >
          <obi-arrow-left-google></obi-arrow-left-google>
        </obc-icon-button>`);e.push(h`<div class="title">${this.appTitle}</div>`);e.push(h`<obc-breadcrumb
          .items=${this.breadcrumbItems}
          @breadcrumb-click=${i=>this.dispatchEvent(new CustomEvent("breadcrumb-click",{detail:i.detail}))}
        ></obc-breadcrumb>`)}else{if(!this.inactive){e.push(h`<div class="menu-button ${this.wideMenuButton?"wide":null}">
            <obc-icon-button
              variant="flat"
              @pointerdown=${()=>this.leftButtonDown(new CustomEvent("menu-button-clicked"))}
              @pointerup=${()=>this.leftButtonUp()}
              @pointerleave=${()=>this.leftButtonLeave()}
              ?activated=${this.menuButtonActivated}
            >
              ${this.menuButtonIcon==="menu"?h`<obi-menu-iec></obi-menu-iec>`:h`<obi-home></obi-home>`}
            </obc-icon-button>
          </div>`)}if(this.showAppIcon){e.push(h`<div class="app-icon"><slot name="app-icon"></slot></div>`)}e.push(h`<div class="title">${this.appTitle}</div>`);e.push(h`<div class="page-name">${this.pageName}</div>`);e.push(h`<slot name="command-button"></slot>`)}const t=Math.max(this.appButtonBreakpointPx,this.dimmingButtonBreakpointPx);return h`
      <style>
                @media (max-width: ${t}px) {
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
        class=${J({wrapper:true,inactive:this.inactive,settings:this.settings,tall:this.tall})}
        role="menubar"
      >
        <div class="left group">${e}</div>
        <div class="right group">
          <div class="alert-container">
            <slot name="alerts"></slot>
          </div>
          ${this.showDimmingButton&&!this.inactive?h`<obc-icon-button
                class="dimming-button"
                part="dimming-button"
                variant="flat"
                @click=${this.dimmingButtonClicked}
                ?activated=${this.dimmingButtonActivated}
              >
                <obi-palette-day-night-iec></obi-palette-day-night-iec>
              </obc-icon-button>`:null}
          ${this.showUserButton&&!this.inactive?h`<obc-icon-button
                class="user-button"
                variant="flat"
                part="user-button"
                @click=${this.userButtonClicked}
                ?activated=${this.userButtonActivated}
                ?disabled=${this.userButtonDisabled}
              >
                <obi-user></obi-user>
              </obc-icon-button>`:null}
          ${this.showAppsButton&&!this.inactive?h`<obc-icon-button
                class="apps-button"
                variant="flat"
                part="apps-button"
                @click=${this.appsButtonClicked}
                ?activated=${this.appsButtonActivated}
              >
                <obi-applications></obi-applications>
              </obc-icon-button>`:null}
          ${this.showClock?h`<slot name="clock"></slot>`:null}
          ${!this.inactive?h`<obc-icon-button
                class="left-more-button"
                part="left-more-button"
                variant="flat"
                @click=${this.leftMoreButtonClicked}
                ?activated=${this.leftMoreButtonActivated}
              >
                <obi-more-vertical-google></obi-more-vertical-google>
              </obc-icon-button>`:null}
        </div>
      </nav>
    `}};Fe.styles=Q(ud);Ye([l({type:String})],Fe.prototype,"appTitle",2);Ye([l({type:String})],Fe.prototype,"pageName",2);Ye([l({type:String})],Fe.prototype,"menuButtonIcon",2);Ye([l({type:Boolean})],Fe.prototype,"menuButtonActivated",2);Ye([l({type:Boolean})],Fe.prototype,"dimmingButtonActivated",2);Ye([l({type:Boolean})],Fe.prototype,"appsButtonActivated",2);Ye([l({type:Boolean})],Fe.prototype,"leftMoreButtonActivated",2);Ye([l({type:Boolean})],Fe.prototype,"userButtonActivated",2);Ye([l({type:Boolean})],Fe.prototype,"userButtonDisabled",2);Ye([l({type:Boolean})],Fe.prototype,"tall",2);Ye([l({type:Boolean})],Fe.prototype,"wideMenuButton",2);Ye([l({type:Boolean})],Fe.prototype,"showAppsButton",2);Ye([l({type:Boolean})],Fe.prototype,"showDimmingButton",2);Ye([l({type:Boolean})],Fe.prototype,"showUserButton",2);Ye([l({type:Boolean})],Fe.prototype,"showClock",2);Ye([l({type:Boolean})],Fe.prototype,"showDate",2);Ye([l({type:Boolean})],Fe.prototype,"showAppIcon",2);Ye([l({type:Boolean})],Fe.prototype,"inactive",2);Ye([l({type:Number})],Fe.prototype,"appButtonBreakpointPx",2);Ye([l({type:Number})],Fe.prototype,"dimmingButtonBreakpointPx",2);Ye([l({type:Number})],Fe.prototype,"appTitleBreakpointPx",2);Ye([l({type:Number})],Fe.prototype,"userButtonBreakpointPx",2);Ye([l({type:Number})],Fe.prototype,"appIconBreakpointPx",2);Ye([l({type:Boolean})],Fe.prototype,"settings",2);Ye([l({type:Array})],Fe.prototype,"breadcrumbItems",2);Fe=Ye([x("obc-top-bar")],Fe);var Vd=L`
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
`;var E4=Object.defineProperty;var R4=Object.getOwnPropertyDescriptor;var Ro=(e,t,i,o)=>{var r=o>1?void 0:o?R4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)E4(t,i,r);return r};var oo=class extends k{constructor(){super(...arguments);this.showTitle=true;this.hasDialog=false;this.dialogTimeOutSeconds=2e4;this.dialogVisibleTimerSeconds=1e4;this.countdownSeconds=0;this.showCountdown=false}render(){const e=this.hasDialog?We`button`:We`section`;return ce`
      <${e} class=${J({wrapper:true,"has-dialog":this.hasDialog})} @click=${this.openDialog}>
        ${!this.showTitle?w:ce`<div class="header">
                <div></div>
                <div class="title">
                  <slot name="title"></slot>
                </div>
                ${this.hasDialog?ce`
                      <obi-chevron-right-google
                        class="icon"
                      ></obi-chevron-right-google>
                    `:ce`<div></div>`}
              </div>`}
        <div class="content">
          <slot></slot>
        </div>
      </${e}>
      ${this.hasDialog?ce`
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
    `}closeDialog(e){e.stopPropagation();this.clearAllTimers();this.removeUserActivityListeners();this.dialog.close()}openDialog(){if(!this.dialog)return;this.dialog.showModal();this.startDialogTimer();this.addUserActivityListeners()}startDialogTimer(){this.clearAllTimers();const e=this.dialogTimeOutSeconds-this.dialogVisibleTimerSeconds;this.countdownStartTimer=window.setTimeout(()=>{this.startCountdown()},e);this.dialogTimer=window.setTimeout(()=>{this.dialog.close();this.clearAllTimers()},this.dialogTimeOutSeconds)}startCountdown(){this.showCountdown=true;const e=performance.now();const t=this.dialogVisibleTimerSeconds;const i=o=>{const r=o-e;const a=Math.max(0,t-r);this.countdownSeconds=a/1e3;if(a<=0){this.clearAllTimers();return}this.countdownTimer=requestAnimationFrame(i)};this.countdownTimer=requestAnimationFrame(i)}clearAllTimers(){if(this.dialogTimer){clearTimeout(this.dialogTimer);this.dialogTimer=void 0}if(this.countdownTimer){cancelAnimationFrame(this.countdownTimer);this.countdownTimer=void 0}if(this.countdownStartTimer){clearTimeout(this.countdownStartTimer);this.countdownStartTimer=void 0}this.showCountdown=false;this.countdownSeconds=0}getProgressPercentage(){const e=this.dialogVisibleTimerSeconds/1e3;const t=this.countdownSeconds/e*100;return Math.max(0,t)}addUserActivityListeners(){this.userActivityHandler=()=>{this.resetDialogTimer()};window.addEventListener("mousemove",this.userActivityHandler);window.addEventListener("touchstart",this.userActivityHandler);window.addEventListener("touchmove",this.userActivityHandler);window.addEventListener("keydown",this.userActivityHandler)}removeUserActivityListeners(){if(this.userActivityHandler){window.removeEventListener("mousemove",this.userActivityHandler);window.removeEventListener("touchstart",this.userActivityHandler);window.removeEventListener("touchmove",this.userActivityHandler);window.removeEventListener("keydown",this.userActivityHandler);this.userActivityHandler=void 0}}resetDialogTimer(){this.clearAllTimers();this.startDialogTimer()}disconnectedCallback(){super.disconnectedCallback();this.clearAllTimers();this.removeUserActivityListeners()}};oo.styles=Q(Vd);Ro([l({type:Boolean,attribute:false})],oo.prototype,"showTitle",2);Ro([l({type:Boolean})],oo.prototype,"hasDialog",2);Ro([l({type:Number})],oo.prototype,"dialogTimeOutSeconds",2);Ro([l({type:Number})],oo.prototype,"dialogVisibleTimerSeconds",2);Ro([Do("dialog")],oo.prototype,"dialog",2);Ro([Ve()],oo.prototype,"countdownSeconds",2);Ro([Ve()],oo.prototype,"showCountdown",2);oo=Ro([x("obc-card")],oo);var Ad=L`
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
`;var $e=e=>e??w;var Zd=L`
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
`;var I4=Object.defineProperty;var N4=Object.getOwnPropertyDescriptor;var Co=(e,t,i,o)=>{var r=o>1?void 0:o?N4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)I4(t,i,r);return r};var Br=class extends k{constructor(){super(...arguments);this.variant="normal";this.fullWidth=false;this.disabled=false;this.showLeadingIcon=false;this.showTrailingIcon=false;this.href=void 0;this.target=void 0;this.segmentPosition="single"}renderLeadingIcon(){if(this.showLeadingIcon){return ce`
        <span class="icon leading" part="icon leading">
          <slot name="leading-icon"></slot>
        </span>
      `}return ce``}renderTrailingIcon(){if(this.showTrailingIcon){return ce`
        <span class="icon trailing" part="icon trailing">
          <slot name="trailing-icon"></slot>
        </span>
      `}return ce``}render(){const e=this.href?We`a`:We`button`;return ce`
      <${e}
        class=${J({wrapper:true,["variant-"+this.variant]:true,hasIconLeading:this.showLeadingIcon,hasIconTrailing:this.showTrailingIcon,"full-width":this.fullWidth,["segment-position-"+this.segmentPosition]:true})}
        ?disabled=${this.disabled}
        href=${$e(this.href)}
        target=${$e(this.target)}
        part="wrapper"
      >
        <div class="visible-wrapper" part="visible-wrapper">
          ${this.renderLeadingIcon()}
          <span class="label" part="label">
            <slot></slot>
          </span>
          ${this.renderTrailingIcon()}
        </div>
      </${e}>
    `}};Br.styles=Q(Zd);Co([l({type:String})],Br.prototype,"variant",2);Co([l({type:Boolean,reflect:true})],Br.prototype,"fullWidth",2);Co([l({type:Boolean})],Br.prototype,"disabled",2);Co([l({type:Boolean})],Br.prototype,"showLeadingIcon",2);Co([l({type:Boolean})],Br.prototype,"showTrailingIcon",2);Co([l({type:String})],Br.prototype,"href",2);Co([l({type:String})],Br.prototype,"target",2);Co([l({type:String})],Br.prototype,"segmentPosition",2);Br=Co([x("obc-button")],Br);var j4=Object.defineProperty;var F4=Object.getOwnPropertyDescriptor;var St=(e,t,i,o)=>{var r=o>1?void 0:o?F4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)j4(t,i,r);return r};var ct=class extends k{constructor(){super(...arguments);this.position="regular";this.size="single-line";this.isClickable=true;this.info=false;this.graphicBorder=false;this.border=false;this.hasAction=false;this.hasLeadingIcon=false;this.hasTrailingIcon=false;this.hasGraphic=false;this.hasStatus=false;this.compact=false;this.directAction=false}render(){let e=this.href?We`a`:We`button`;e=!this.isClickable?We`article`:e;if(this.overrideTag!==void 0){switch(this.overrideTag){case"a":e=We`a`;break;case"button":e=We`button`;break;case"article":e=We`article`;break;case"div":e=We`div`;break;default:throw new Error("Invalid tag")}}if(this.hasAction){e=We`article`;this.isClickable=false}return ce`
    <div class="wrapper ${this.position}">
        <${e} class=${J({button:true,[this.position]:true,[this.size]:true,"graphic-border":this.graphicBorder,info:this.info,border:this.border,"has-leading-icon":this.hasLeadingIcon,"has-trailing-icon":this.hasTrailingIcon,"has-graphic":this.hasGraphic,"has-status":this.hasStatus,"not-clickable":!this.isClickable,"has-action":this.hasAction,compact:this.compact,"direct-action":this.directAction})}
        part="wrapper" href=${$e(this.href)} target=${$e(this.target)}>
          ${this.hasGraphic?ce`<div class="graphic"><slot name="graphic"></slot></div>`:w}
          <div class="content-container" part="content-container">
            <div class="container-content">
              ${this.hasLeadingIcon?ce`<div class="leading-icon" part="leading-icon">
                      <slot name="leading-icon"></slot>
                    </div>`:w}
              <div class="content" part="label">
                <slot name="label"></slot>
                ${this.size==="single-line"?w:ce`<slot name="description"></slot>`}
              </div>
            </div>
            ${this.hasStatus?ce`<div class="status" part="status">
                    <slot name="status"></slot>
                  </div>`:w}
            ${this.hasAction?ce`<obc-button
                    variant="normal"
                    class="action"
                    part="action"
                    @click=${()=>{this.dispatchEvent(new CustomEvent("action-click"))}}
                  >
                    <slot name="action"></slot>
                  </obc-button>`:w}
            ${this.hasTrailingIcon?ce`<div class="trailing-icon" part="trailing-icon">
                    <slot name="trailing-icon"></slot>
                  </div>`:w}
          </div>
        </${e}>
        </div>
    `}};ct.styles=Q(Ad);St([l({type:String})],ct.prototype,"position",2);St([l({type:String})],ct.prototype,"size",2);St([l({type:String})],ct.prototype,"overrideTag",2);St([l({type:Boolean,attribute:false})],ct.prototype,"isClickable",2);St([l({type:Boolean})],ct.prototype,"info",2);St([l({type:Boolean})],ct.prototype,"graphicBorder",2);St([l({type:Boolean})],ct.prototype,"border",2);St([l({type:Boolean})],ct.prototype,"hasAction",2);St([l({type:Boolean})],ct.prototype,"hasLeadingIcon",2);St([l({type:Boolean})],ct.prototype,"hasTrailingIcon",2);St([l({type:Boolean})],ct.prototype,"hasGraphic",2);St([l({type:Boolean})],ct.prototype,"hasStatus",2);St([l({type:Boolean})],ct.prototype,"compact",2);St([l({type:Boolean})],ct.prototype,"directAction",2);St([l({type:String})],ct.prototype,"href",2);St([l({type:String})],ct.prototype,"target",2);ct=St([x("obc-elevated-card")],ct);var Td=L`
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
`;var U4=Object.defineProperty;var W4=Object.getOwnPropertyDescriptor;var Ne=(e,t,i,o)=>{var r=o>1?void 0:o?W4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)U4(t,i,r);return r};var Be=class extends k{constructor(){super(...arguments);this.value="";this.unit="";this.placeholder="";this.textAlign="right";this.disabled=false;this.readonly=false;this.error=false;this.errorText="";this.rejectUpdatesOnFocus=false;this.rejectUpdates=false;this.rejectDuplicateUpdates=false;this.name="";this.size="regular";this.hasLeadingIcon=false;this.helperText="";this.label="";this.required=false;this.hasLabelIcon=false;this.labelPlacement="left";this.hasHelperIcon=false;this.helperPlacement="left";this.squared=false;this.hasFocus=false;this.previousValue="";this.previousInputElementValue=""}onInput(e){this.value=e.target.value;this.previousInputElementValue=this.value}onFocus(){this.hasFocus=true}onBlur(){this.hasFocus=false}get shouldUpdateValue(){if(this.rejectUpdates)return false;if(this.rejectUpdatesOnFocus&&this.hasFocus)return false;if(this.rejectDuplicateUpdates&&this.value===this.previousValue){return false}return true}willUpdate(e){if(e.has("value")&&!this.shouldUpdateValue&&this.inputElement){this.value=this.inputElement.value}}updated(){if(this.rejectDuplicateUpdates&&this.value!==this.previousValue&&(this.previousInputElementValue!==this.value||!this.hasFocus)){this.previousValue=this.value}}renderFooterText(e,t){if(!e)return w;return h`<div
      id="helper-text"
      class=${J({[t?"error-text":"helper-text"]:true,[`helper-placement-${this.helperPlacement}`]:true})}
    >
      ${this.hasHelperIcon?h`<div class="helper-icon"><slot name="helper-icon"></slot></div>`:w}
      ${e}
    </div>`}render(){const e=Boolean(this.helperText)||Boolean(this.error&&this.errorText);const t=this.unit&&this.textAlign!=="right-unit-outside";const i=this.unit&&this.textAlign==="right-unit-outside";let o=this.value;if(!this.shouldUpdateValue&&this.inputElement){o=this.inputElement.value}return h`
      <label
        class=${J({wrapper:true,[`align-${this.textAlign}`]:true,[`size-${this.size}`]:true,error:this.error,disabled:this.disabled,helpertext:e,haslabel:Boolean(this.label),squared:this.squared})}
      >
        ${this.label?h`<div
              class=${J({"label-text-container":true,[`label-placement-${this.labelPlacement}`]:true})}
            >
              ${this.hasLabelIcon?h`<div class="label-icon">
                    <slot name="label-icon"></slot>
                  </div>`:w}
              <span class="label-text">${this.label}</span>
              ${this.required?h`<div class="required-indicator"></div>`:w}
            </div>`:w}

        <div class="horizontal-container">
          <div class="input-field-container">
            ${this.hasLeadingIcon?h`<div class="leading-icon">
                  <slot name="leading-icon"></slot>
                </div>`:w}
            <div class="label-container">
              <input
                type="text"
                inputmode="decimal"
                class="value-input"
                .value=${o}
                @focus=${this.onFocus}
                @blur=${this.onBlur}
                .placeholder=${this.placeholder}
                name=${$e(this.name||void 0)}
                ?disabled=${this.disabled}
                ?readonly=${this.readonly}
                ?required=${this.required}
                maxlength=${$e(this.maxlength)}
                minlength=${$e(this.minlength)}
                aria-invalid=${this.error?"true":"false"}
                aria-describedby=${$e(e?"helper-text":void 0)}
                autocomplete="off"
                @input=${this.onInput}
              />
              ${t?h`<span class="unit-text">${this.unit}</span>`:w}
            </div>
          </div>
          ${i?h`<span class="unit-text external">${this.unit}</span>`:w}
        </div>

        ${this.error&&this.errorText?this.renderFooterText(this.errorText,true):this.renderFooterText(this.helperText,false)}
      </label>
    `}};Be.styles=Q(Td);Ne([l({type:String})],Be.prototype,"value",2);Ne([l({type:String})],Be.prototype,"unit",2);Ne([l({type:String})],Be.prototype,"placeholder",2);Ne([l({type:String})],Be.prototype,"textAlign",2);Ne([l({type:Boolean,reflect:true})],Be.prototype,"disabled",2);Ne([l({type:Boolean,reflect:true})],Be.prototype,"readonly",2);Ne([l({type:Boolean,reflect:true})],Be.prototype,"error",2);Ne([l({type:String})],Be.prototype,"errorText",2);Ne([l({type:Boolean})],Be.prototype,"rejectUpdatesOnFocus",2);Ne([l({type:Boolean})],Be.prototype,"rejectUpdates",2);Ne([l({type:Boolean})],Be.prototype,"rejectDuplicateUpdates",2);Ne([l({type:String})],Be.prototype,"name",2);Ne([l({type:Number})],Be.prototype,"maxlength",2);Ne([l({type:Number})],Be.prototype,"minlength",2);Ne([l({type:String})],Be.prototype,"size",2);Ne([l({type:Boolean})],Be.prototype,"hasLeadingIcon",2);Ne([l({type:String})],Be.prototype,"helperText",2);Ne([l({type:String})],Be.prototype,"label",2);Ne([l({type:Boolean})],Be.prototype,"required",2);Ne([l({type:Boolean})],Be.prototype,"hasLabelIcon",2);Ne([l({type:String})],Be.prototype,"labelPlacement",2);Ne([l({type:Boolean})],Be.prototype,"hasHelperIcon",2);Ne([l({type:String})],Be.prototype,"helperPlacement",2);Ne([l({type:Boolean})],Be.prototype,"squared",2);Ne([Ve()],Be.prototype,"hasFocus",2);Ne([Ve()],Be.prototype,"previousValue",2);Ne([Ve()],Be.prototype,"previousInputElementValue",2);Ne([Do(".value-input")],Be.prototype,"inputElement",2);Be=Ne([x("obc-number-input-field")],Be);var Pd=L`
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
`;var G4=Object.defineProperty;var q4=Object.getOwnPropertyDescriptor;var Ua=(e,t,i,o)=>{var r=o>1?void 0:o?q4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)G4(t,i,r);return r};var mi=class extends k{constructor(){super(...arguments);this.transparentTrack=false;this._thumbTop=0;this._thumbHeight=0;this._showOverlayThumb=false;this._resizeObserver=null;this._scrollHandler=null;this._wrapper=null}render(){return h`
      <div
        class=${J({wrapper:true,"transparent-track":this.transparentTrack})}
      >
        <slot></slot>
      </div>
      ${this.transparentTrack&&this._showOverlayThumb?h`<div class="overlay-track">
            <div
              class="overlay-thumb"
              style="top:${this._thumbTop}%;height:${this._thumbHeight}%"
            ></div>
          </div>`:w}
    `}firstUpdated(){this._wrapper=this.shadowRoot?.querySelector(".wrapper")??null;if(this._wrapper){this._resizeObserver=new ResizeObserver(()=>{this._checkOverflow();this._updateOverlayThumb()});this._resizeObserver.observe(this._wrapper);const e=this._wrapper.querySelector("slot");e?.addEventListener("slotchange",()=>{this._checkOverflow();this._updateOverlayThumb()});if(this.transparentTrack){this._scrollHandler=()=>this._updateOverlayThumb();this._wrapper.addEventListener("scroll",this._scrollHandler,{passive:true})}}}disconnectedCallback(){super.disconnectedCallback();this._resizeObserver?.disconnect();this._resizeObserver=null;if(this._scrollHandler&&this._wrapper){this._wrapper.removeEventListener("scroll",this._scrollHandler);this._scrollHandler=null}this._wrapper=null}_updateOverlayThumb(){if(!this.transparentTrack)return;if(!this._wrapper)return;const{scrollHeight:e,clientHeight:t,scrollTop:i}=this._wrapper;if(e<=t){this._showOverlayThumb=false;return}this._showOverlayThumb=true;const o=t;const r=parseFloat(getComputedStyle(this._wrapper).getPropertyValue("--menu-navigation-components-scroll-bar-padding"))||4;const a=o-r*2;const n=t/e*a;const p=r+i/e*a;this._thumbTop=p/o*100;this._thumbHeight=n/o*100}_checkOverflow(){if(!this._wrapper)return;const e=this._wrapper.scrollHeight>this._wrapper.clientHeight;this.toggleAttribute("overflowing",e)}scrollToBottom(){if(!this._wrapper){throw new Error("Wrapper not found")}this._wrapper.scrollTop=this._wrapper.scrollHeight}};mi.styles=Q(Pd);Ua([l({type:Boolean,attribute:"transparent-track"})],mi.prototype,"transparentTrack",2);Ua([Ve()],mi.prototype,"_thumbTop",2);Ua([Ve()],mi.prototype,"_thumbHeight",2);Ua([Ve()],mi.prototype,"_showOverlayThumb",2);mi=Ua([x("obc-scrollbar")],mi);var zd=L`
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
`;var Y4=Object.defineProperty;var Q4=Object.getOwnPropertyDescriptor;var Bd=(e,t,i,o)=>{var r=o>1?void 0:o?Q4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Y4(t,i,r);return r};var Xn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13 20L13 7.83L18.59 13.42L20 12L12 4L4 12L5.41 13.41L11 7.83L11 20L13 20Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13 20L13 7.83L18.59 13.42L20 12L12 4L4 12L5.41 13.41L11 7.83L11 20L13 20Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Xn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Bd([l({type:Boolean})],Xn.prototype,"useCssColor",2);Xn=Bd([x("obi-arrow-up-google")],Xn);var K4=Object.defineProperty;var X4=Object.getOwnPropertyDescriptor;var Od=(e,t,i,o)=>{var r=o>1?void 0:o?X4(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)K4(t,i,r);return r};var Jn=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11 4L11 16.17L5.41 10.58L4 12L12 20L20 12L18.59 10.59L13 16.17L13 4L11 4Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11 4L11 16.17L5.41 10.58L4 12L12 20L20 12L18.59 10.59L13 16.17L13 4L11 4Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Jn.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Od([l({type:Boolean})],Jn.prototype,"useCssColor",2);Jn=Od([x("obi-arrow-down-google")],Jn);var J4=Object.defineProperty;var eu=Object.getOwnPropertyDescriptor;var Dd=(e,t,i,o)=>{var r=o>1?void 0:o?eu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)J4(t,i,r);return r};var el=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7.11508 18.7051L5.70508 17.2951L11.7051 11.2951L17.7051 17.2951L16.2951 18.7051L11.7051 14.1251L7.11508 18.7051Z" fill="currentColor"/>
<path d="M7.11508 12.7052L5.70508 11.2952L11.7051 5.29517L17.7051 11.2952L16.2951 12.7052L11.7051 8.12517L7.11508 12.7052Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7.11508 18.7051L5.70508 17.2951L11.7051 11.2951L17.7051 17.2951L16.2951 18.7051L11.7051 14.1251L7.11508 18.7051Z" style="fill: var(--element-active-color)"/>
<path d="M7.11508 12.7052L5.70508 11.2952L11.7051 5.29517L17.7051 11.2952L16.2951 12.7052L11.7051 8.12517L7.11508 12.7052Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};el.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Dd([l({type:Boolean})],el.prototype,"useCssColor",2);el=Dd([x("obi-chevron-double-up-google")],el);var tu=Object.defineProperty;var ru=Object.getOwnPropertyDescriptor;var Ed=(e,t,i,o)=>{var r=o>1?void 0:o?ru(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)tu(t,i,r);return r};var tl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M16.2948 5.29487L17.7048 6.70487L11.7048 12.7049L5.70483 6.70487L7.11483 5.29487L11.7048 9.87487L16.2948 5.29487Z" fill="currentColor"/>
<path d="M16.2948 11.2948L17.7048 12.7048L11.7048 18.7048L5.70483 12.7048L7.11483 11.2948L11.7048 15.8748L16.2948 11.2948Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M16.2948 5.29487L17.7048 6.70487L11.7048 12.7049L5.70483 6.70487L7.11483 5.29487L11.7048 9.87487L16.2948 5.29487Z" style="fill: var(--element-active-color)"/>
<path d="M16.2948 11.2948L17.7048 12.7048L11.7048 18.7048L5.70483 12.7048L7.11483 11.2948L11.7048 15.8748L16.2948 11.2948Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};tl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ed([l({type:Boolean})],tl.prototype,"useCssColor",2);tl=Ed([x("obi-chevron-double-down-google")],tl);var ou=Object.defineProperty;var iu=Object.getOwnPropertyDescriptor;var Rd=(e,t,i,o)=>{var r=o>1?void 0:o?iu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)ou(t,i,r);return r};var rl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M18.41 16.59L17 18L11 12L17 6L18.41 7.41L13.83 12L18.41 16.59Z" fill="currentColor"/>
<path d="M12.41 16.59L11 18L5 12L11 6L12.41 7.41L7.83 12L12.41 16.59Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M18.41 16.59L17 18L11 12L17 6L18.41 7.41L13.83 12L18.41 16.59Z" style="fill: var(--element-active-color)"/>
<path d="M12.41 16.59L11 18L5 12L11 6L12.41 7.41L7.83 12L12.41 16.59Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};rl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Rd([l({type:Boolean})],rl.prototype,"useCssColor",2);rl=Rd([x("obi-chevron-double-left-google")],rl);var au=Object.defineProperty;var nu=Object.getOwnPropertyDescriptor;var Id=(e,t,i,o)=>{var r=o>1?void 0:o?nu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)au(t,i,r);return r};var ol=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5 7.41L6.41 6L12.41 12L6.41 18L5 16.59L9.58 12L5 7.41Z" fill="currentColor"/>
<path d="M11 7.41L12.41 6L18.41 12L12.41 18L11 16.59L15.58 12L11 7.41Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5 7.41L6.41 6L12.41 12L6.41 18L5 16.59L9.58 12L5 7.41Z" style="fill: var(--element-active-color)"/>
<path d="M11 7.41L12.41 6L18.41 12L12.41 18L11 16.59L15.58 12L11 7.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ol.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Id([l({type:Boolean})],ol.prototype,"useCssColor",2);ol=Id([x("obi-chevron-double-right-google")],ol);var lu=Object.defineProperty;var su=Object.getOwnPropertyDescriptor;var Nd=(e,t,i,o)=>{var r=o>1?void 0:o?su(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)lu(t,i,r);return r};var il=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" fill="currentColor"/>
<path d="M8 11C7.44772 11 7 11.4477 7 12C7 12.5523 7.44772 13 8 13H16C16.5523 13 17 12.5523 17 12C17 11.4477 16.5523 11 16 11H8Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" style="fill: var(--element-active-color)"/>
<path d="M8 11C7.44772 11 7 11.4477 7 12C7 12.5523 7.44772 13 8 13H16C16.5523 13 17 12.5523 17 12C17 11.4477 16.5523 11 16 11H8Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};il.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Nd([l({type:Boolean})],il.prototype,"useCssColor",2);il=Nd([x("obi-off")],il);var cu=Object.defineProperty;var du=Object.getOwnPropertyDescriptor;var jd=(e,t,i,o)=>{var r=o>1?void 0:o?du(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)cu(t,i,r);return r};var al=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2ZM12 4C16.4183 4 20 7.58172 20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4Z" fill="currentColor"/>
<path d="M12 6C13.1046 6 14 6.89543 14 8L14 16C14 17.1046 13.1046 18 12 18C10.8954 18 10 17.1046 10 16L10 8C10 6.89543 10.8954 6 12 6Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2ZM12 4C16.4183 4 20 7.58172 20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4Z" style="fill: var(--element-active-color)"/>
<path d="M12 6C13.1046 6 14 6.89543 14 8L14 16C14 17.1046 13.1046 18 12 18C10.8954 18 10 17.1046 10 16L10 8C10 6.89543 10.8954 6 12 6Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};al.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;jd([l({type:Boolean})],al.prototype,"useCssColor",2);al=jd([x("obi-on")],al);var pu=Object.defineProperty;var hu=Object.getOwnPropertyDescriptor;var Fd=(e,t,i,o)=>{var r=o>1?void 0:o?hu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)pu(t,i,r);return r};var nl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 2C13.733 2 15.1492 3.35645 15.2449 5.06546L15.25 5.24987L15.251 13.202L15.331 13.2709C16.2565 14.0975 16.8482 15.2418 16.9746 16.4939L16.9936 16.7457L17 17C17 19.7614 14.7614 22 12 22C9.23858 22 7 19.7614 7 17C7 15.6373 7.5496 14.3655 8.48922 13.4396L8.66993 13.2701L8.749 13.202L8.75 5.25C8.75 3.57886 10.0113 2.20232 11.6339 2.0204L11.8156 2.00514L12 2ZM12 3.5C11.0818 3.5 10.3288 4.20711 10.2558 5.10651L10.25 5.25004L10.2495 13.9445L9.94128 14.1691C9.04185 14.8246 8.5 15.8664 8.5 17C8.5 18.933 10.067 20.5 12 20.5C13.933 20.5 15.5 18.933 15.5 17C15.5 15.9376 15.0241 14.9558 14.2239 14.2971L14.0595 14.1697L13.7515 13.9451L13.75 5.25C13.75 4.2835 12.9665 3.5 12 3.5ZM12 7C12.4142 7 12.75 7.33579 12.75 7.75L12.7506 14.6146C13.7646 14.9334 14.5 15.8808 14.5 17C14.5 18.3807 13.3807 19.5 12 19.5C10.6193 19.5 9.5 18.3807 9.5 17C9.5 15.8804 10.2359 14.9328 11.2504 14.6143L11.25 7.75C11.25 7.33579 11.5858 7 12 7Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 2C13.733 2 15.1492 3.35645 15.2449 5.06546L15.25 5.24987L15.251 13.202L15.331 13.2709C16.2565 14.0975 16.8482 15.2418 16.9746 16.4939L16.9936 16.7457L17 17C17 19.7614 14.7614 22 12 22C9.23858 22 7 19.7614 7 17C7 15.6373 7.5496 14.3655 8.48922 13.4396L8.66993 13.2701L8.749 13.202L8.75 5.25C8.75 3.57886 10.0113 2.20232 11.6339 2.0204L11.8156 2.00514L12 2ZM12 3.5C11.0818 3.5 10.3288 4.20711 10.2558 5.10651L10.25 5.25004L10.2495 13.9445L9.94128 14.1691C9.04185 14.8246 8.5 15.8664 8.5 17C8.5 18.933 10.067 20.5 12 20.5C13.933 20.5 15.5 18.933 15.5 17C15.5 15.9376 15.0241 14.9558 14.2239 14.2971L14.0595 14.1697L13.7515 13.9451L13.75 5.25C13.75 4.2835 12.9665 3.5 12 3.5ZM12 7C12.4142 7 12.75 7.33579 12.75 7.75L12.7506 14.6146C13.7646 14.9334 14.5 15.8808 14.5 17C14.5 18.3807 13.3807 19.5 12 19.5C10.6193 19.5 9.5 18.3807 9.5 17C9.5 15.8804 10.2359 14.9328 11.2504 14.6143L11.25 7.75C11.25 7.33579 11.5858 7 12 7Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};nl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Fd([l({type:Boolean})],nl.prototype,"useCssColor",2);nl=Fd([x("obi-temperature-air")],nl);var uu=Object.defineProperty;var fu=Object.getOwnPropertyDescriptor;var ia=(e,t,i,o)=>{var r=o>1?void 0:o?fu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)uu(t,i,r);return r};var Io=class extends k{constructor(){super(...arguments);this.readouts=[];this.tag=null;this.size="regular";this.idTagOrientation="top";this.hasIdTag=false}renderTag(){if(!this.hasIdTag||!this.tag)return h``;const e=this.tag.value.toString().padStart(4,"0");return h`<div class="tag">#${e}</div>`}renderValueContainer(e,t,i){return h`<div class="readout-item ${e}">
      ${t}
      <div class="value-container">
        <div class="label-container">${i}</div>
      </div>
    </div>`}renderValueText(e){return h`<span class="value-text">${e}</span>`}renderValue(e){const t=e.value.toFixed(0);const i=t.length<e.nDigits?"0".repeat(e.nDigits-t.length):"";const o=i+t;let r=w;if(e.icon=="arrow"){if(e.direction=="up"){r=h`<obi-arrow-up-google
          class="icon"
          useCssColor
        ></obi-arrow-up-google>`}else if(e.direction=="down"){r=h`<obi-arrow-down-google
          class="icon"
          useCssColor
        ></obi-arrow-down-google>`}else if(e.direction=="left"){r=h`<obi-arrow-left-google
          class="icon"
          useCssColor
        ></obi-arrow-left-google>`}else if(e.direction=="right"){r=h`<obi-arrow-right-google
          class="icon"
          useCssColor
        ></obi-arrow-right-google>`}}else if(e.icon=="chevron"){if(e.direction=="up"){r=h`<obi-chevron-double-up-google
          class="icon"
          useCssColor
        ></obi-chevron-double-up-google>`}else if(e.direction=="down"){r=h`<obi-chevron-double-down-google
          class="icon"
          useCssColor
        ></obi-chevron-double-down-google>`}else if(e.direction=="left"){r=h`<obi-chevron-double-left-google
          class="icon"
          useCssColor
        ></obi-chevron-double-left-google>`}else if(e.direction=="right"){r=h`<obi-chevron-double-right-google
          class="icon"
          useCssColor
        ></obi-chevron-double-right-google>`}}const a=h`
      ${this.renderValueText(o)}
      <span class="unit">${e.unit}</span>
    `;return this.renderValueContainer("value",r,a)}renderStateOff(e){let t=h``;if(e.hasIcon){t=h`<obi-off class="icon" useCssColor></obi-off>`}const i=this.renderValueText(e.value);return this.renderValueContainer("state-off",t,i)}renderStateOn(e){let t=h``;if(e.hasIcon){t=h`<obi-on class="icon" useCssColor></obi-on>`}const i=this.renderValueText(e.value);return this.renderValueContainer("state-on",t,i)}renderButton(e){const t=e.value.toFixed(1);let i=h``;if(e.hasIcon){i=h`<obi-temperature-air
        class="icon"
        useCssColor
      ></obi-temperature-air>`}const o=h`
      ${this.renderValueText(t)}
      <span class="unit">${e.unit}</span>
    `;return h`<obc-button class="readout-button" part="readout-button">
      ${this.renderValueContainer("button",i,o)}
    </obc-button>`}renderReadout(e){if(e.type==="value"){return this.renderValue(e)}else if(e.type==="state-on"){return this.renderStateOn(e)}else if(e.type==="state-off"){return this.renderStateOff(e)}else if(e.type==="button"){return this.renderButton(e)}else{throw new Error("Invalid readout type")}}render(){const e=this.readouts.filter(r=>r.type==="value"||r.type==="state-off"||r.type==="state-on"||r.type==="button");const t=e.map(r=>this.renderReadout(r));const i=this.renderTag();const o=[];if(this.idTagOrientation==="top"){if(this.hasIdTag)o.push(i);o.push(...t)}else{o.push(...t);if(this.hasIdTag)o.push(i)}return h`<div class="readout-stack ${this.size}">${o}</div>`}};Io.styles=Q(zd);ia([l({attribute:false})],Io.prototype,"readouts",2);ia([l({attribute:false})],Io.prototype,"tag",2);ia([l()],Io.prototype,"size",2);ia([l()],Io.prototype,"idTagOrientation",2);ia([l({type:Boolean})],Io.prototype,"hasIdTag",2);Io=ia([x("obc-automation-button-readout-stack")],Io);function ll(e,t){if(t.strokePosition==="center"){return c`<circle id=${e} cx="0" cy="0" 
      r=${t.radius} vector-effect="non-scaling-stroke" 
      stroke=${t.strokeColor}  stroke-width=${t.strokeWidth} 
      fill=${t.fillColor}>`}else if(t.strokePosition==="inside"){return c`
		<defs>
			<clipPath id="clip${e}">
				<circle id=${e} cx="0" cy="0" r=${t.radius} vector-effect="non-scaling-stroke" />
			</clipPath>
		</defs>
		<g>
			<circle id=${e} cx="0" cy="0" r=${t.radius} vector-effect="non-scaling-stroke" stroke=${t.strokeColor}  stroke-width=${t.strokeWidth*2} fill=${t.fillColor} clip-path="url(#clip${e})"/>
		</g>
  `}else{return c`
		<circle id=${e} cx="0" cy="0" r=${t.radius} vector-effect="non-scaling-stroke" stroke=${t.strokeColor} stroke-width=${t.strokeWidth*2} fill=${t.fillColor}/>
		  `}}var Le=(e=>{e["active"]="active";e["loading"]="loading";e["off"]="off";return e})(Le||{});var me=(e=>{e["regular"]="regular";e["enhanced"]="enhanced";return e})(me||{});var Wa=(e=>{e["regular"]="regular";e["flat"]="flat";e["framed"]="framed";e["instrument"]="instrument";return e})(Wa||{});var Or=(e=>{e["innerFirstChild"]="innerFirstChild";e["middleChild"]="middleChild";e["middleRoundedChild"]="middleRoundedChild";e["outerLastChild"]="outerLastChild";return e})(Or||{});var at=(e=>{e["notEqual"]="notEqual";e["equal"]="equal";e["equalZero"]="equalZero";e["focus"]="focus";return e})(at||{});var gi=(e=>{e["enhanced"]="enhanced";e["regular"]="regular";return e})(gi||{});var vu="M22.5918 0.5C25.014 0.50013 26.3186 3.34437 24.917 5.29199L15.0244 19.0371C14.0268 20.423 11.9635 20.423 10.9658 19.0371L1.07326 5.29199C-0.328328 3.34437 0.97623 0.500124 3.39845 0.5L22.5918 0.5Z";var mu=13;var gu=21;var bu=.8;var yu=4;var wu=8;var sl=300;var io="--setpoint-animation-duration";var ko="300ms";function cl(e){const t=getComputedStyle(e).getPropertyValue(io).trim();if(!t)return sl;const i=parseFloat(t);if(Number.isNaN(i))return sl;if(t.endsWith("s")&&!t.endsWith("ms"))return i*1e3;return i}function Ud(e,t){const i=(t%360+360)%360;const o=(e%360+360)%360;let r=i-o;if(r>180)r-=360;if(r<-180)r+=360;return e+r}function Cu(e,t,i=false){if(i){return"var(--instrument-frame-tertiary-color)"}if(e==="focus"){if(t==="enhanced"){return"var(--base-blue-100)"}else{return"var(--instrument-regular-tertiary-color)"}}if(t==="enhanced"){return"var(--instrument-enhanced-primary-color)"}else{return"var(--instrument-regular-primary-color)"}}function ku(e,t){if(e==="focus"){if(t==="enhanced"){return"var(--element-neutral-enhanced-color)"}else{return"var(--instrument-regular-secondary-color)"}}return"var(--border-silhouette-color)"}function Lu(e){return vu}function xu(e){switch(e){case"equal":case"equalZero":return bu;default:return 1}}function No(e){switch(e){case"equalZero":return wu;case"notEqual":case"focus":return yu;default:return 0}}function Wd(e="setpoint"){return`${e}-${Math.random().toString(36).slice(2,9)}`}function nr(e){const{visualState:t,colorMode:i,disabled:o=false,id:r}=e;const a=Cu(t,i,o);const n=ku(t,i);const p=Lu();const d=xu(t);const f=`${r}-marker`;const g=`${r}-mask`;const m=-mu;const u=-gu;const M=`scale(${d})`;const C=t==="focus";return c`
    <defs>
      <g id="${f}">
        <path
          fill-rule="evenodd"
          clip-rule="evenodd"
          transform="translate(${m}, ${u})"
          d="${p}"
          vector-effect="non-scaling-stroke"
        />
      </g>
      <mask id="${g}">
        <rect x="-20" y="-30" width="50" height="50" fill="white" />
        <use href="#${f}" fill="black" />
      </mask>
    </defs>
    <g transform="${M}" style="transition: transform 200ms ease-in-out;">
      <use href="#${f}" fill="${a}" stroke="none" />
      ${C?c`
          <!-- Focus state: 1px silhouette (outer) + 2px colored border (inner) -->
          <!-- First: masked silhouette stroke for outer 1px edge -->
          <use
            href="#${f}"
            mask="url(#${g})"
            fill="none"
            stroke="var(--border-silhouette-color)"
            stroke-width="4"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
          <!-- Second: 2px colored border on top -->
          <use
            href="#${f}"
            fill="none"
            stroke="${n}"
            stroke-width="2"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
        `:c`
          <use
            href="#${f}"
            mask="url(#${g})"
            fill="none"
            stroke="${n}"
            stroke-width="2"
            stroke-linejoin="round"
            vector-effect="non-scaling-stroke"
          />
        `}
    </g>
  `}function Gd(e){const{state:t,priority:i,atSetpoint:o,angleSetpoint:r,setpointAtZeroDeadband:a=.5,newAngleSetpoint:n,touching:p=false,setpointOverride:d=false}=e;const f=n!==void 0;const g=i===me.enhanced?"enhanced":"regular";if(t===Le.loading||t===Le.off){return{visualState:"notEqual",colorMode:g,disabled:!d,hasNewSetpoint:f}}if(p&&!f){return{visualState:"focus",colorMode:g,disabled:false,hasNewSetpoint:f}}const m=r!==void 0&&Math.abs(r)<a;if(o&&m){return{visualState:"equalZero",colorMode:g,disabled:false,hasNewSetpoint:f}}if(o){return{visualState:"equal",colorMode:g,disabled:false,hasNewSetpoint:f}}return{visualState:"notEqual",colorMode:g,disabled:false,hasNewSetpoint:f}}var f1=168;function aa(e){const{value:t,setpoint:i,touching:o,auto:r,deadband:a,atSetpointManual:n,angularWraparound:p=false}=e;if(t===void 0||i===void 0)return false;if(o)return false;if(r){let d=Math.abs(t-i);if(p&&d>180){d=360-d}const f=Number.isFinite(a)?a:0;return d<=f}return n}function Ga({startAngle:e,endAngle:t,r:i,R:o,roundOutsideCut:r,roundInsideCut:a}){const n=e*Math.PI/180;const p=t*Math.PI/180;const d=Math.sin(n)*o;const f=-Math.cos(n)*o;const g=Math.sin(n)*i;const m=-Math.cos(n)*i;const u=Math.sin(p)*o;const M=-Math.cos(p)*o;const C=Math.sin(p)*i;const A=-Math.cos(p)*i;const H=8;let _="";if(r){const S=Math.asin(H/o);const E=p-S-(n+S)<=Math.PI?0:1;const D=Math.sin(n)*(o-H);const K=-Math.cos(n)*(o-H);const I=Math.sin(n+S)*o;const Y=-Math.cos(n+S)*o;const R=Math.sin(p)*(o-H);const B=-Math.cos(p)*(o-H);const F=Math.sin(p-S)*o;const z=-Math.cos(p-S)*o;_+=`M ${D} ${K} A ${H} ${H} 1 0 1 ${I} ${Y}`;_+=`A ${o} ${o} 1 ${E} 1 ${F} ${z}`;_+=`A ${H} ${H} 1 0 1 ${R} ${B}`}else{const S=Math.abs(p-n)<=Math.PI?0:1;_+=`M ${d} ${f} A ${o} ${o} 1 ${S} 1 ${u} ${M}`}if(a){const S=Math.asin(H/i);const E=p-S-(n+S)<=Math.PI?0:1;const D=Math.sin(n)*(i+H);const K=-Math.cos(n)*(i+H);const I=Math.sin(n+S)*i;const Y=-Math.cos(n+S)*i;const R=Math.sin(p)*(i+H);const B=-Math.cos(p)*(i+H);const F=Math.sin(p-S)*i;const z=-Math.cos(p-S)*i;_+=`L ${R} ${B} A ${H} ${H} 1 0 1 ${F} ${z}`;_+=`A ${i} ${i} 1 ${E} 0 ${I} ${Y}`;_+=`A ${H} ${H} 1 0 1 ${D} ${K}`}else{const S=p-n<=Math.PI?0:1;_+=`L ${C} ${A} A ${i} ${i} 1 ${S} 0 ${g} ${m}`}_+=`Z`;return _}var qd=L`
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
`;var{I:$u}=cd;var Yd=e=>e;var Kd=e=>void 0===e.strings;var Qd=()=>document.createComment("");var na=(e,t,i)=>{const o=e._$AA.parentNode,r=void 0===t?e._$AB:t._$AA;if(void 0===i){const a=o.insertBefore(Qd(),r),n=o.insertBefore(Qd(),r);i=new $u(a,n,e,e.options)}else{const a=i._$AB.nextSibling,n=i._$AM,p=n!==e;if(p){let d;i._$AQ?.(e),i._$AM=e,void 0!==i._$AP&&(d=e._$AU)!==n._$AU&&i._$AP(d)}if(a!==r||p){let d=i._$AA;for(;d!==a;){const f=Yd(d).nextSibling;Yd(o).insertBefore(d,r),d=f}}}return i};var jo=(e,t,i=e)=>(e._$AI(t,i),e);var Mu={};var Xd=(e,t=Mu)=>e._$AH=t;var Jd=e=>e._$AH;var dl=e=>{e._$AR(),e._$AA.remove()};var qa=(e,t)=>{const i=e._$AN;if(void 0===i)return false;for(const o of i)o._$AO?.(t,false),qa(o,t);return true};var pl=e=>{let t,i;do{if(void 0===(t=e._$AM))break;i=t._$AN,i.delete(e),e=t}while(0===i?.size)};var e2=e=>{for(let t;t=e._$AM;e=t){let i=t._$AN;if(void 0===i)t._$AN=i=new Set;else if(i.has(e))break;i.add(e),_u(t)}};function Hu(e){void 0!==this._$AN?(pl(this),this._$AM=e,e2(this)):this._$AM=e}function Su(e,t=false,i=0){const o=this._$AH,r=this._$AN;if(void 0!==r&&0!==r.size)if(t)if(Array.isArray(o))for(let a=i;a<o.length;a++)qa(o[a],false),pl(o[a]);else null!=o&&(qa(o,false),pl(o));else qa(this,e)}var _u=e=>{e.type==Eo.CHILD&&(e._$AP??=Su,e._$AQ??=Hu)};var hl=class extends to{constructor(){super(...arguments),this._$AN=void 0}_$AT(t,i,o){super._$AT(t,i,o),e2(this),this.isConnected=t._$AU}_$AO(t,i=true){t!==this.isConnected&&(this.isConnected=t,t?this.reconnected?.():this.disconnected?.()),i&&(qa(this,t),pl(this))}setValue(t){if(Kd(this._$Ct))this._$Ct._$AI(t,this);else{const i=[...this._$Ct._$AH];i[this._$Ci]=t,this._$Ct._$AI(i,this,0)}}disconnected(){}reconnected(){}};var Lo=class{constructor(t,{target:i,config:o,callback:r,skipInitial:a}){this.t=new Set,this.o=false,this.i=false,this.h=t,null!==i&&this.t.add(i??t),this.l=o,this.o=a??this.o,this.callback=r,pd||(window.ResizeObserver?(this.u=new ResizeObserver(n=>{this.handleChanges(n),this.h.requestUpdate()}),t.addController(this)):console.warn("ResizeController error: browser does not support ResizeObserver."))}handleChanges(t){this.value=this.callback?.(t,this.u)}hostConnected(){for(const t of this.t)this.observe(t)}hostDisconnected(){this.disconnect()}async hostUpdated(){!this.o&&this.i&&this.handleChanges([]),this.i=false}observe(t){this.t.add(t),this.u.observe(t,this.l),this.i=true,this.h.requestUpdate()}unobserve(t){this.t.delete(t),this.u.unobserve(t)}disconnect(){this.u.disconnect()}target(t){return Vu(this,t)}};var Vu=wo(class extends hl{constructor(){super(...arguments),this.observing=false}render(e,t){}update(e,[t,i]){this.controller=t,this.part=e,this.observe=i,false===i?(t.unobserve(e.element),this.observing=false):false===this.observing&&(t.observe(e.element),this.observing=true)}disconnected(){this.controller?.unobserve(this.part.element),this.observing=false}reconnected(){false!==this.observe&&false===this.observing&&(this.controller?.observe(this.part.element),this.observing=true)}});var Te=(e=>{e["zeroLineThick"]="zeroLineThick";e["zeroLine"]="zeroLine";e["main"]="main";e["primary"]="primary";e["secondary"]="secondary";e["tertiary"]="tertiary";e["textOnly"]="textOnly";return e})(Te||{});var He=(e=>{e["regular"]="regular";e["enhanced"]="enhanced";return e})(He||{});function bi(e,t){if(e==="regular"){return"var(--instrument-tick-mark-tertiary-color)"}else{if(t==="tertiary"){return"var(--instrument-tick-mark-secondary-color)"}return"var(--instrument-tick-mark-primary-color)"}}function yi(e,{size:t,style:i,scale:o,text:r,inside:a,textRadius:n,rotation:p,maxDigits:d,color:f,radiusOffset:g=0}){if(o===Infinity||o<0){throw new Error("Tick scale is not valid")}const m=g;let u;let M;n=n+(3/o+3)*(a?-1:1);const C=e*Math.PI/180;if(t==="primary"){u=328/2+m;M=368/2+m}else if(t==="secondary"){u=328/2+m;M=344/2+m}else if(t==="main"||t==="zeroLine"){u=320/2+m;M=368/2+m}else if(t==="zeroLineThick"){u=224/2+m;M=368/2+m}else if(t==="tertiary"){u=328/2+m;M=336/2+m}else{return[t2(r??"",e,a,o,n)]}if(a){const I=368/2+m;const Y=320/2+m;const R=M-u;const B=Math.max(0,u-Y);M=I-B;u=M-R}const A=f??bi(i,t);const H=Math.sin(C)*u;const _=-Math.cos(C)*u;const S=Math.sin(C)*M;const E=-Math.cos(C)*M;const D=t==="zeroLine"||t==="zeroLineThick"?4:1;const K=c`<line x1=${H} y1=${_} x2=${S} y2=${E} stroke=${A} stroke-width=${D} vector-effect="non-scaling-stroke"/>`;if(r){if(p===void 0){return[K,t2(r,e,a,o,n)]}else{const I=n+(4/o+5)*(a?-1:1)*d/2;const Y=Math.sin(C)*I;const R=-Math.cos(C)*I;return[K,c`<text x=${Y} y=${R} class="label rotate ${a?"inside":""}" transform="rotate(${-p})" transform-origin="${Y} ${R}">${r}</text>`]}}return K}function t2(e,t,i,o,r){let a;if(t===0){a="top"}else if(t<180&&t>0){a="right"}else if(t===180){a="bottom"}else{a="left"}const n=t*Math.PI/180;const p=i?-1:1;const d=7/o*p;const f=6/o*p;let g=Math.sin(n)*(r+f);if(t>180){g+=4/o*p}else if(t<180&&t>0){g-=4/o*p}const m=-Math.cos(n)*(r+d);return c`<text x=${g} y=${m} class="label ${a} ${i?"inside":""}">${e}</text>`}var dt=(e=>{e["advice"]="advice";e["caution"]="caution";return e})(dt||{});var de=(e=>{e["regular"]="regular";e["hinted"]="hinted";e["triggered"]="triggered";return e})(de||{});var Au=(344-328)/2+8;var v1=Math.atan2(Au,(344+328)/2);function la(e,t,i,o,r=0){const a=((t-e)%360+360)%360;const n=a*Math.PI/180;if(n<=v1*2)return w;const p=e*Math.PI/180+v1;const d=t*Math.PI/180-v1;const f=328/2+r;const g=344/2+r;const m=(g-f)/2;const u=Math.sin(p)*f;const M=-Math.cos(p)*f;const C=Math.sin(p)*g;const A=-Math.cos(p)*g;const H=Math.sin(d)*f;const _=-Math.cos(d)*f;const S=Math.sin(d)*g;const E=-Math.cos(d)*g;const D=`M ${u} ${M} 
                    A ${f} ${f} 0 0 1 ${H} ${_}
                    A ${m} ${m} 0 0 0 ${S} ${E}
                    A ${g} ${g} 0 0 0 ${C} ${A}
                    A ${m} ${m} 0 0 0 ${u} ${M}
                    Z`;return c`<path d=${D} fill=${i} stroke=${o} stroke-width="1" vector-effect="non-scaling-stroke" />`}function r2(e,t=0){if(e.type==="caution"){let i;let o=null;if(e.state==="hinted"){i="var(--instrument-frame-tertiary-color)"}else if(e.state==="regular"){i="var(--instrument-tick-mark-tertiary-color)"}else{i="var(--on-caution-active-color)";o="var(--alert-caution-color)"}const r=[];if(t>0){const u=328/2+t;const M=344/2+t;const C=(u+M)/2;const A=2*Math.PI*168/90;const H=Math.round(2*Math.PI*C/A);const _=.705;const S=u-12;const E=M+12;const D=Math.tan(_)*(E-S)/(2*C);for(let K=0;K<H;K++){const I=K*2*Math.PI/H;const Y=S*Math.sin(I-D);const R=-S*Math.cos(I-D);const B=E*Math.sin(I+D);const F=-E*Math.cos(I+D);r.push(c`<line x1=${Y} y1=${R} x2=${B} y2=${F} stroke=${i} stroke-width="4"/>`)}}else{for(let u=0;u<180;u+=4){r.push(c`<g transform="rotate(${u}) translate(-256 -256) ">
            <path d="M369.167 64.7317L144 194.732L142 191.268L367.167 61.2676L369.167 64.7317ZM369.167 320.732L144 450.732L142 447.267L367.167 317.267L369.167 320.732Z" fill=${i}/>
            </g>
            `)}}const a=`adviceMask-${e.minAngle}-${e.maxAngle}`;let n=He.regular;if(e.state==="regular"){n=He.regular}else if(e.state==="triggered"){n=He.enhanced}const p=t>0?"none":"black";const d=la(e.minAngle,e.maxAngle,"white",p,t);const f=la(e.minAngle,e.maxAngle,"none",i,t);let g;let m;if(t>0){const u=344/2+t+32;g=c`<mask id=${a} maskUnits="userSpaceOnUse" x="${-u}" y="${-u}" width="${u*2}" height="${u*2}">${d}</mask>`;m=o?c`<rect x="${-u}" y="${-u}" width="${u*2}" height="${u*2}" fill="${o}"/>`:w}else{g=c`<mask id=${a}>${d}</mask>`;m=o?c`<rect x="-256" y="-256" width="512" height="512" fill="${o}"/>`:w}return c`
            ${g}
            <g mask="url(#${a})">
                ${m}
                ${r}
            </g>
            ${f}
            ${e.hideMinTickmark?w:yi(e.minAngle,{size:Te.primary,style:n,scale:1,inside:false,textRadius:0,maxDigits:0,radiusOffset:t})}
            ${e.hideMaxTickmark?w:yi(e.maxAngle,{size:Te.primary,style:n,scale:1,inside:false,textRadius:0,maxDigits:0,radiusOffset:t})}
        `}else{let i;let o;if(e.state==="hinted"){i="var(--instrument-frame-tertiary-color)";o=He.regular}else if(e.state==="regular"){i="var(--instrument-regular-secondary-color)";o=He.regular}else{i="var(--instrument-enhanced-secondary-color)";o=He.regular}return c`
            ${la(e.minAngle,e.maxAngle,e.state==="triggered"?i:"none",i,t)}
            ${yi(e.minAngle,{size:Te.primary,style:o,scale:1,inside:false,textRadius:0,maxDigits:0,radiusOffset:t})}
            ${yi(e.maxAngle,{size:Te.primary,style:o,scale:1,inside:false,textRadius:0,maxDigits:0,radiusOffset:t})}
        `}}var sa=(e=>{e["dots"]="dots";e["bar"]="bar";return e})(sa||{});var Ya=(e=>{e["scale"]="scale";e["innerCircle"]="innerCircle";return e})(Ya||{});var m1=5;var o2=Array.from({length:m1},(e,t)=>360/m1*t);var Zu=172;var Tu=100;var kr=8;var Pu=kr;var zu=kr*.75-kr*.25;var Qa=.05;function Ka(e,t=0){const i=e==="scale"?Zu:Tu;return i+t}function i2(e,t){const i=e*Math.PI/180;return{cx:Math.sin(i)*t,cy:-Math.cos(i)*t}}function a2(e,t,i=0){const o=Ka(t,i);return c`${o2.map(r=>{const{cx:a,cy:n}=i2(r,o);return c`<circle cx="${a}" cy="${n}" r="${Pu}" fill="${e}" />`})}`}function Bu(e,t,i){const o=i+kr;const r=i-kr;const a=e*Math.PI/180;const n=t*Math.PI/180;const p=Math.sin(a)*o;const d=-Math.cos(a)*o;const f=Math.sin(a)*r;const g=-Math.cos(a)*r;const m=Math.sin(n)*o;const u=-Math.cos(n)*o;const M=Math.sin(n)*r;const C=-Math.cos(n)*r;const A=((n-a)%(2*Math.PI)+2*Math.PI)%(2*Math.PI);let H;let _;if(A<=Math.PI){H=1;_=0}else{H=0;_=1}return[`M ${p} ${d}`,`A ${o} ${o} 0 0 ${H} ${m} ${u}`,`A ${kr} ${kr} 0 0 ${H} ${M} ${C}`,`A ${r} ${r} 0 0 ${_} ${f} ${g}`,`Z`].join(" ")}function g1(e,t){const i=((t-e)%360+360)%360;return i<=180?i:360-i}function b1(e,t=0){const i=Ka(e,t);return kr/i*(180/Math.PI)}function n2(e,t,i,o=0){const r=Ka(i,o);const a=kr;const n=kr*2;const p=kr/2;return c`
    <g transform="rotate(${t})">
      <rect
        x="${-a/2}"
        y="${-r-n/2}"
        width="${a}"
        height="${n}"
        rx="${p}"
        fill="${e}"
      />
    </g>
  `}function l2(e){const{startAngle:t,endAngle:i,barColor:o,position:r,maskId:a="rot-bar-mask",radiusOffset:n=0}=e;if(g1(t,i)<b1(r,n)){return c``}const p=Ka(r,n);const d=Bu(t,i,p);return c`
    <defs>
      <clipPath id="${a}">
        <path d="${d}" />
      </clipPath>
    </defs>
    <path d="${d}" fill="${o}" />
  `}function s2(e,t,i=0){const o=Ka(t,i);return c`
    ${o2.map(r=>{const{cx:a,cy:n}=i2(r,o);return c`<circle cx="${a}" cy="${n}" r="${zu}" fill="${e}" />`})}
  `}var Qy=360/m1;var Ky=kr/2;var ul=class{constructor(t,i,o=1,r=0){this._rotationsPerMinute=1;this._cyclePx=0;this.host=t;this.el=i;this._rotationsPerMinute=o;this._cyclePx=r;this.host.addController(this)}set rotationsPerMinute(t){if(this._rotationsPerMinute!==t){this._rotationsPerMinute=t;this.updateAnimation()}}get rotationsPerMinute(){return this._rotationsPerMinute}set cyclePx(t){if(this._cyclePx!==t){this._cyclePx=t;this.updateAnimation()}}get cyclePx(){return this._cyclePx}get isTranslateMode(){return this._cyclePx>0}getKeyframes(){if(this.isTranslateMode){return[{transform:"translateX(0px)"},{transform:`translateX(${this._cyclePx}px)`}]}return[{transform:"rotate(0deg)"},{transform:"rotate(360deg)"}]}hostConnected(){this.startAnimation()}startAnimation(){const t=Math.abs(this._rotationsPerMinute);const i=t===0?1:1e3*60/t;this.animation=this.el.animate(this.getKeyframes(),{duration:i,iterations:Infinity,direction:this._rotationsPerMinute>=0?"normal":"reverse"});if(this._rotationsPerMinute===0){this.animation.pause()}}updateAnimation(){if(!this.animation)return;const t=this.animation.effect.getComputedTiming();const i=t.duration;const o=this.animation.currentTime??0;const r=t.direction;const a=o%i/i;this.animation.cancel();const n=Math.abs(this._rotationsPerMinute);const p=n===0?1:1e3*60/n;const d=this._rotationsPerMinute>=0?"normal":"reverse";const f=r!==d?1-a:a;this.animation=this.el.animate(this.getKeyframes(),{duration:p,iterations:Infinity,direction:d});this.animation.currentTime=f*p;if(this._rotationsPerMinute===0){this.animation.pause()}}destroy(){this.animation?.cancel();this.animation=void 0}hostDisconnected(){this.destroy()}};function fl(e,t){if(t){t.destroy();e.removeController(t)}return void 0}function y1(e){const{scale:t,inside:i,innerRadius:o,includeNorth:r}=e;const a=16;const n=8;const p=368/2;const d=m=>m*(i?o-n/t-a/2:p+n/t+a/2);const f=[{label:"E",x:d(1),y:0},{label:"S",x:0,y:d(1)},{label:"W",x:d(-1),y:0}];const g=t<.58;if(r||g||i){f.push({label:"N",x:0,y:d(-1)})}return f}function c2(e,t){let i;let o;let r;let a;let n;if(typeof e==="number"){i=e;o=t;r=false;a=368/2}else{i=e.scale;o=e.rotation;r=e.inside??false;a=e.innerRadius??368/2;n=e.includeNorth}const p=y1({scale:i,inside:r,innerRadius:a,includeNorth:n});return c`
    ${p.map(d=>c`
        <text
          x="${d.x}"
          y="${d.y}"
          class="label"
          transform="rotate(${-(o??0)})"
          transform-origin="${d.x} ${d.y}"
        >
          ${d.label}
        </text>
      `)}
  `}function d2(e){const{scale:t,rotation:i,inside:o=false}=e;const r=368/2;const a=t<.58;if(a){if(o){return c`
        <g transform="translate(0, ${-r})">
          <path fill-rule="evenodd" clip-rule="evenodd"
            d="M-17.8457 24.984 0 0 17.8458 24.984C11.9868 24.3338 6.0324 24 0 24-6.0323 24-11.9867 24.3338-17.8457 24.984Z"
            fill="var(--instrument-frame-tertiary-color)"/>
        </g>`}else{return c`
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
        </g>`}}if(o){return c`
      <path transform="translate(-256, -256)" fill-rule="evenodd" clip-rule="evenodd"
        d="M238.152 96.9842L255.998 72L273.844 96.9839C267.985 96.3338 262.031 96 256 96C249.967 96 244.012 96.3339 238.152 96.9842Z"
        fill="var(--instrument-frame-tertiary-color)"/>
    `}return c`
    <g transform="translate(0, ${(1/t-1)*188}) scale(${1/t})">
      <path transform="translate(-192, -224)"
        d="M 221.521 35.425 C 222.388 36.4644 222.821 36.9841 222.809 37.3627 C 222.8 37.6941 222.632 37.9916 222.354 38.1721 C 222.037 38.3783 221.361 38.2774 220.011 38.0756 A ${188*t} ${188*t} 0 0 0 163.989 38.0756 C 162.639 38.2774 161.964 38.3783 161.646 38.1721 C 161.368 37.9916 161.201 37.6941 161.191 37.3627 C 161.18 36.9841 161.613 36.4644 162.479 35.425 L 190.771 1.475 C 191.193 0.9685 191.404 0.7153 191.657 0.6229 C 191.879 0.5419 192.122 0.5419 192.343 0.6229 C 192.596 0.7153 192.807 0.9685 193.229 1.475 L 221.521 35.425 Z"
        fill="var(--instrument-tick-mark-secondary-color)"/>
    </g>

    <defs>
      <mask id="circleMask">
        <rect x="-${r}" y="-${r}" width="${r*2}" height="${r*2}" fill="black"/>
        <circle cx="0" cy="0" r="${r}" fill="white"/>
      </mask>
    </defs>
    <g mask="url(#circleMask)" transform="translate(0, ${-(r+10/t+30)}) scale(${.75/t}, ${.75/t}) rotate(${-(i??0)})" transform-origin="0 25">
      <path d="M5.003 29H2.091L-3.013 20.264H-3.077C-3.066 20.52-3.056 20.7813-3.045 21.048-3.034 21.3147-3.024 21.5867-3.013 21.864-2.992 22.1307-2.976 22.4027-2.965 22.68-2.954 22.9573-2.944 23.2347-2.933 23.512V29H-4.997V17.576H-2.101L2.987 26.232H3.035C3.024 25.9867 3.014 25.736 3.003 25.48 2.992 25.2133 2.982 24.952 2.971 24.696 2.971 24.4293 2.966 24.1627 2.955 23.896 2.944 23.6293 2.934 23.3627 2.923 23.096V17.576H5.003V29Z" fill="var(--element-active-inverted-color)"/>
    </g>
  `}var p2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M92 66.6364H83.7941L83.1324 65.4385L84.2794 62.1943H85.2941L82.4265 60.9964H82.0735L81.8057 59.7842C81.7044 59.3261 81.2984 59 80.8292 59H79.1708C78.7016 59 78.2956 59.3261 78.1943 59.7842L77.9265 60.9964H77.5735L74.7059 62.1943H75.7206L76.8676 65.4385L76.2059 66.6364H68V67.0856H69.3235V70.2299H68V79.3137V80.0624L68.5089 82.024C68.9278 83.639 70.1096 84.8535 71.5707 85.1706L80 87L88.4293 85.1706C89.8904 84.8535 91.0722 83.639 91.4911 82.024L92 80.0624V79.3137V70.2299V66.6364ZM86.3529 71.9657V79.3137H70.081V71.9657H86.3529Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92 80.0624L91.4911 82.024C91.0722 83.639 89.8904 84.8535 88.4293 85.1706L80 87L71.5707 85.1706C70.1096 84.8535 68.9278 83.639 68.5089 82.024L68 80.0624M92 80.0624H68M92 80.0624V79.3137M83.7941 66.6364H92V70.2299M83.7941 66.6364L83.1324 65.4385M83.7941 66.6364H76.2059M83.1324 65.4385L84.2794 62.1943M83.1324 65.4385H76.8676M84.2794 62.1943H85.2941L82.4265 60.9964H82.0735M84.2794 62.1943H75.7206M68 80.0624V79.3137M76.2059 66.6364H68V67.0856H69.3235V70.2299M76.2059 66.6364L76.8676 65.4385M76.8676 65.4385L75.7206 62.1943M75.7206 62.1943H74.7059L77.5735 60.9964H77.9265M68 79.3137H70.081M68 79.3137V70.2299H69.3235M92 79.3137H86.3529M92 79.3137V70.2299M86.3529 79.3137V71.9657H70.081V79.3137M86.3529 79.3137H70.081M69.3235 70.2299H92M82.0735 60.9964H81.7206H78.2794H77.9265M82.0735 60.9964L81.8057 59.7842C81.7044 59.3261 81.2984 59 80.8292 59H79.1708C78.7016 59 78.2956 59.3261 78.1943 59.7842L77.9265 60.9964" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var h2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 74.9115L13.0001 73.5L48.0001 73L52.8784 68.1352H75.4774L76.1648 65.6631L75.0908 62.3099H74.3605L76.6374 60H83.3628L85.6396 62.3099H84.9093L83.8353 65.6631L84.5227 68.1352H107.122L112 73L147 73.5L150 74.9115L150 80.16L147 81.8885L146.846 83.4086C146.791 83.95 146.452 84.3687 146.031 84.4377C145.96 84.4493 145.89 84.4476 145.818 84.4479C144.806 84.451 136.713 84.4895 128.544 84.9172C124.018 85.1541 118.577 85.6275 113.488 86.1336C102.356 87.2408 91.1872 88 80.0001 88C68.813 88 57.6441 87.2408 46.5119 86.1336C41.4228 85.6275 35.9817 85.1541 31.456 84.9172C23.2869 84.4895 15.194 84.451 14.182 84.4479C14.1104 84.4476 14.0397 84.4493 13.969 84.4377C13.5479 84.3687 13.2092 83.95 13.1543 83.4086L13.0001 81.8885L10.0001 80.16L10 74.9115Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M48.0001 73L13.0001 73.5L10 74.9115L10.0001 80.16M48.0001 73L52.8784 68.1352H75.4774M48.0001 73H112M75.4774 68.1352L76.1648 65.6631M75.4774 68.1352H84.5227M76.1648 65.6631L75.0908 62.3099M76.1648 65.6631H83.8353M75.0908 62.3099H74.3605L76.6374 60H83.3628L85.6396 62.3099H84.9093M75.0908 62.3099H84.9093M10.0001 80.16L13.0001 81.8885L13.1543 83.4086C13.2092 83.95 13.5479 84.3687 13.969 84.4377C14.0397 84.4493 14.1104 84.4476 14.182 84.4479C15.194 84.451 23.2869 84.4895 31.456 84.9172C35.9817 85.1541 41.4228 85.6275 46.5119 86.1336C57.6441 87.2408 68.813 88 80.0001 88C91.1872 88 102.356 87.2408 113.488 86.1336C118.577 85.6275 124.018 85.1541 128.544 84.9172C136.713 84.4895 144.806 84.451 145.818 84.4479C145.89 84.4476 145.96 84.4493 146.031 84.4377C146.452 84.3687 146.791 83.95 146.846 83.4086L147 81.8885L150 80.16M10.0001 80.16H150M112 73L147 73.5L150 74.9115L150 80.16M112 73L107.122 68.1352H84.5227M84.5227 68.1352L83.8353 65.6631M83.8353 65.6631L84.9093 62.3099" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var u2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80.0007 151.999C73.373 152 68 146.627 68 139.999L68 128.776L68 104.642L68 56.7557L68 19.9992C68 13.3717 73.3726 7.99916 80 7.99916C86.6274 7.99916 92 13.3717 92 19.9992L92 23.108L92 56.7557L92 108.092L92 137.357L92 139.999C92 146.626 86.6278 151.999 80.0007 151.999Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M85.8387 85.9422L73.9677 85.9422L73.9677 74.336L85.8387 74.336L85.8387 85.9422Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M92 108.092L86.2419 108.092M92 108.092L92 56.7557M92 108.092L92 137.357M86.2419 108.092L84.4516 104.642L72.9355 104.642L68 104.642M86.2419 108.092L86.2419 137.357L92 137.357M68 104.642L68 128.776L68 139.999C68 146.627 73.373 152 80.0007 151.999V151.999C86.6278 151.999 92 146.626 92 139.999L92 137.357M68 104.642L68 56.7557M68 56.7557L68 19.9992C68 13.3717 73.3726 7.99916 80 7.99916V7.99916V7.99916C86.6274 7.99916 92 13.3717 92 19.9992L92 23.108M68 56.7557L86.2419 56.7557M92 56.7557L86.2419 56.7557M92 56.7557L92 23.108M86.2419 56.7557L86.2419 23.108L92 23.108M73.9677 85.9422L85.8387 85.9422M73.9677 85.9422L73.9677 74.336M73.9677 85.9422L76.5806 83.424M85.8387 85.9422L85.8387 74.336M85.8387 85.9422L83.2258 83.424M85.8387 74.336L73.9677 74.336M85.8387 74.336L83.2258 76.8541M73.9677 74.336L76.5806 76.8541M76.5806 83.424L83.2258 83.424M76.5806 83.424L76.5806 76.8541M83.2258 83.424L83.2258 76.8541M83.2258 76.8541L76.5806 76.8541" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var f2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var v2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71H18.4844V63L22 44H26V63H32.4844V53.5604V50.1099L31 48.9973L32 48.1429H37.4294L37.2747 38.5H39.5L41.88 48.1429H45.8152C48.7962 48.1429 51.7388 48.8152 54.4239 50.1099H52.5695L50.3443 53.5604V71H117.416L124.833 64.1236H148C148 64.1236 146.5 67 144.5 71C143.302 73.3966 143.5 75.6209 143.5 75.6209C145.701 75.6209 147.484 77.4047 147.484 79.6053V80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71H18.4844M147.484 80V79.6053C147.484 77.4047 145.701 75.6209 143.5 75.6209V75.6209C143.5 75.6209 143.302 73.3966 144.5 71C146.5 67 148 64.1236 148 64.1236H124.833L117.416 71H50.3443M18.4844 71H50.3443M18.4844 71V63L22 44H26V63H32.4844V53.5604M32.4844 53.5604H50.3443M32.4844 53.5604V50.1099M50.3443 53.5604L52.5695 50.1099H32.4844M50.3443 53.5604V71M32.4844 50.1099H54.4239V50.1099C51.7388 48.8152 48.7962 48.1429 45.8152 48.1429H41.88M32.4844 50.1099L31 48.9973L32 48.1429H37.4294M41.88 48.1429L39.5 38.5H37.2747L37.4294 48.1429M41.88 48.1429H37.4294" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="136" cy="70" r="2" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var m2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 122L64 122L64 118L72 118L75 114L85 114L88 118L96 118L96 122L86 122L86 138.75L74 138.75L74 122Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var g2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var b2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var y2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 140L64 140L64 128L72 128L75 124L85 124L88 128L96 128L96 140L86 140L86 148.75L74 148.75L74 140Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 21.6677C78.2643 22.1593 79.8323 23.5259 80.5811 25.3486L80.7239 25.7307L83.565 34.1692L77.6776 27.4895C76.2735 25.8965 75.7779 23.7047 76.3472 21.6677Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 45.6667C78.2643 46.1584 79.8323 47.5249 80.5811 49.3476L80.7239 49.7297L83.565 58.1682L77.6776 51.4885C76.2735 49.8955 75.7779 47.7037 76.3472 45.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 69.6667C78.2643 70.1584 79.8323 71.5249 80.5811 73.3476L80.7239 73.7297L83.565 82.1682L77.6776 75.4885C76.2735 73.8955 75.7779 71.7037 76.3472 69.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M76.3472 93.6667C78.2643 94.1584 79.8323 95.5249 80.5811 97.3476L80.7239 97.7297L83.565 106.168L77.6776 99.4885C76.2735 97.8955 75.7779 95.7037 76.3472 93.6667Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var w2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M132.366 87.1181H29.3855V83.0385L20.4844 80V71.5412H24V68.7912H20.4844V66.0412H24V51.1429H31.5L36 66.0412H48L51.5 71.5412H54.4157L55.575 61.5604L54.0915 57.1099H52.608L54.4157 54.1429H57.4294L54.4624 44.5H56.6877L61.88 54.1429C65.3312 54.1429 68.772 54.5206 72.1409 55.2692L80.4239 57.1099H78.5695L76.3443 61.5604L88.5 71.0827C102.374 69.3897 109.424 63.1236 109.424 63.1236H118L115.5 51.1429H118L122 63.1236H140.743C132 69.5 130.325 77.1044 130.325 77.1044L135.162 76.321C137.428 75.9539 139.484 77.7039 139.484 80C139.484 83.9312 136.297 87.1181 132.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M20.4844 80H139.484M20.4844 80L29.3855 83.0385V87.1181H132.366C136.297 87.1181 139.484 83.9312 139.484 80V80M20.4844 80V71.5412H24V68.7912H20.4844V66.0412H24M139.484 80V80C139.484 77.7039 137.428 75.9539 135.162 76.321L130.325 77.1044C130.325 77.1044 132 69.5 140.743 63.1236H122M54.4157 71.5412C54.4157 71.5412 75.9997 71.5 81.5 71.5C100 71.5 109.424 63.1236 109.424 63.1236H118M54.4157 71.5412L55.575 61.5604M54.4157 71.5412H51.5L48 66.0412H36M55.575 61.5604H76.3443M55.575 61.5604L54.0915 57.1099H78.5695L76.3443 61.5604M76.3443 61.5604L88.5 71.0827M61.88 54.1429V54.1429C65.3312 54.1429 68.772 54.5206 72.1409 55.2692L80.4239 57.1099H52.608L54.4157 54.1429H57.4294M61.88 54.1429L56.6877 44.5H54.4624L57.4294 54.1429M61.88 54.1429H57.4294M24 66.0412V51.1429H31.5L36 66.0412M24 66.0412H36M122 63.1236L118 51.1429H115.5L118 63.1236M122 63.1236H118" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var C2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M80 18.25C80 18.25 93.5 18.25 93.5 51.1402L93.5 94.2378L93.5 122L93.5 128L93.5 135L93.5 139.75C93.5 140.855 92.6046 141.75 91.5 141.75L90.125 141.75L69.875 141.75L68.5 141.75C67.3954 141.75 66.5 140.855 66.5 139.75L66.5 135L66.5 128L66.5 122L66.5 51.1402C66.5 18.25 80 18.25 80 18.25Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 135L66.5 139.75C66.5 140.855 67.3954 141.75 68.5 141.75L69.875 141.75L90.125 141.75L91.5 141.75C92.6046 141.75 93.5 140.855 93.5 139.75L93.5 135M66.5 135L93.5 135M66.5 135L66.5 128M93.5 135L93.5 128M93.5 122L93.5 94.2378L93.5 51.1402C93.5 18.25 80 18.25 80 18.25C80 18.25 66.5 18.25 66.5 51.1402L66.5 122M93.5 122L93.5 128M93.5 122L88 122L88 128M93.5 128L88 128M66.5 128L66.5 122M66.5 128L72 128M88 128L72 128M66.5 122L72 122L72 128M82 34L81.5 42.5L78.5 42.5L78 34L82 34Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71 103.375L64.25 103.375L64.25 94.375C64.25 94.375 67.4029 89.009 69.5 86C71.7705 82.7422 75.5 78.625 75.5 78.625L84.5 78.625C84.5 78.625 87.8347 82.9839 90 86C92.2512 89.1357 95.75 94.375 95.75 94.375L95.75 103.375L89 103.375L85.625 103.5L74.375 103.5L71 103.375Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.375 103.5L71 103.375L64.25 103.375L64.25 94.375C64.25 94.375 67.4029 89.009 69.5 86C71.7705 82.7422 75.5 78.625 75.5 78.625M74.375 103.5L85.625 103.5M74.375 103.5L74.375 91C74.6384 86.5926 75.5 78.625 75.5 78.625M85.625 103.5L89 103.375L95.75 103.375L95.75 94.375C95.75 94.375 92.2512 89.1357 90 86C87.8347 82.9839 84.5 78.625 84.5 78.625M85.625 103.5L85.625 91C85.3616 86.5925 84.5 78.625 84.5 78.625M84.5 78.625L75.5 78.625" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 97.625L85.625 103.25L83.375 104.375L76.625 104.375L74.375 103.25L74.375 97.625L76.625 101L83.375 101L85.625 97.625Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 101L85.625 97.625L85.625 103.25L83.375 104.375M83.375 101L76.625 101M83.375 101L83.375 104.375M76.625 101L74.375 97.625L74.375 103.25L76.625 104.375M76.625 101L76.625 104.375M76.625 104.375L83.375 104.375" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var k2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M68 66.6364H76.2059L76.8676 65.4385L75.7206 62.1943H74.7059L77.5735 60.9964H77.9265L78.1943 59.7842C78.2956 59.3261 78.7016 59 79.1708 59H80.8292C81.2984 59 81.7044 59.3261 81.8057 59.7842L82.0735 60.9964H82.4265L85.2941 62.1943H84.2794L83.1324 65.4385L83.7941 66.6364H92V67.0856H90.6765V70.2299H92V79.3137V80.0624L91.4911 82.024C91.0722 83.639 89.8904 84.8535 88.4293 85.1706L80 87L71.5707 85.1706C70.1096 84.8535 68.9278 83.639 68.5089 82.024L68 80.0624V79.3137V70.2299V66.6364ZM73.6471 71.9657V79.3137H89.919V71.9657H73.6471Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M68 80.0624L68.5089 82.024C68.9278 83.639 70.1096 84.8535 71.5707 85.1706L80 87L88.4293 85.1706C89.8904 84.8535 91.0722 83.639 91.4911 82.024L92 80.0624M68 80.0624H92M68 80.0624V79.3137M76.2059 66.6364H68V70.2299M76.2059 66.6364L76.8676 65.4385M76.2059 66.6364H83.7941M76.8676 65.4385L75.7206 62.1943M76.8676 65.4385H83.1324M75.7206 62.1943H74.7059L77.5735 60.9964H77.9265M75.7206 62.1943H84.2794M92 80.0624V79.3137M83.7941 66.6364H92V67.0856H90.6765V70.2299M83.7941 66.6364L83.1324 65.4385M83.1324 65.4385L84.2794 62.1943M84.2794 62.1943H85.2941L82.4265 60.9964H82.0735M92 79.3137H89.919M92 79.3137V70.2299H90.6765M68 79.3137H73.6471M68 79.3137V70.2299M73.6471 79.3137V71.9657H89.919V79.3137M73.6471 79.3137H89.919M90.6765 70.2299H68M77.9265 60.9964H78.2794H81.7206H82.0735M77.9265 60.9964L78.1943 59.7842C78.2956 59.3261 78.7016 59 79.1708 59H80.8292C81.2984 59 81.7044 59.3261 81.8057 59.7842L82.0735 60.9964" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var L2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<mask id="path-1-inside-1_208_29995" fill="white">
<path d="M125.032 93.6077C139.926 93.6077 152 81.5337 152 66.6396L11.7453 66.6396L11.7453 93.6076L125.032 93.6077Z"/>
</mask>
<path d="M125.032 93.6077C139.926 93.6077 152 81.5337 152 66.6396L11.7453 66.6396L11.7453 93.6076L125.032 93.6077Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M152 66.6396L154 66.6396L154 64.6396L152 64.6396L152 66.6396ZM11.7453 66.6396L11.7453 64.6396L9.74529 64.6396L9.74529 66.6396L11.7453 66.6396ZM11.7453 93.6076L9.74528 93.6076L9.74528 95.6076L11.7453 95.6076L11.7453 93.6076ZM125.032 95.6077C141.031 95.6077 154 82.6382 154 66.6396L150 66.6396C150 80.4291 138.821 91.6077 125.032 91.6077L125.032 95.6077ZM152 64.6396L11.7453 64.6396L11.7453 68.6396L152 68.6396L152 64.6396ZM9.74529 66.6396L9.74528 93.6076L13.7453 93.6076L13.7453 66.6396L9.74529 66.6396ZM11.7453 95.6076L125.032 95.6077L125.032 91.6077L11.7453 91.6076L11.7453 95.6076Z" fill="var(--instrument-tick-mark-secondary-color)" mask="url(#path-1-inside-1_208_29995)"/>
</svg>
`;var x2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<mask id="path-1-inside-1_208_29982" fill="white">
<path fill-rule="evenodd" clip-rule="evenodd" d="M80 9.18359C71.6308 14.0249 66 23.0737 66 33.4377L66 151.06L94 151.06L94 33.4377C94 23.0737 88.3692 14.0249 80 9.18359Z"/>
</mask>
<path fill-rule="evenodd" clip-rule="evenodd" d="M80 9.18359C71.6308 14.0249 66 23.0737 66 33.4377L66 151.06L94 151.06L94 33.4377C94 23.0737 88.3692 14.0249 80 9.18359Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M80 9.18359L81.0014 7.45238L80 6.87307L78.9985 7.45238L80 9.18359ZM66 151.06L64 151.06L64 153.06L66 153.06L66 151.06ZM94 151.06L94 153.06L96 153.06L96 151.06L94 151.06ZM68 33.4377C68 23.8165 73.2248 15.4133 81.0014 10.9148L78.9985 7.45238C70.0367 12.6365 64 22.3309 64 33.4377L68 33.4377ZM64 33.4377L64 151.06L68 151.06L68 33.4377L64 33.4377ZM66 153.06L94 153.06L94 149.06L66 149.06L66 153.06ZM96 151.06L96 33.4377L92 33.4377L92 151.06L96 151.06ZM96 33.4377C96 22.3309 89.9633 12.6365 81.0014 7.45238L78.9985 10.9148C86.7752 15.4133 92 23.8165 92 33.4377L96 33.4377Z" fill="var(--instrument-tick-mark-secondary-color)" mask="url(#path-1-inside-1_208_29982)"/>
</svg>
`;var $2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var M2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var H2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71.5412H92.5943L105.575 58.5604L104.092 54.1099H102.608L104.092 52.9973H106.688V51.1429H107.429L104.462 41.5H106.688L111.88 51.1429C115.331 51.1429 118.772 51.5206 122.141 52.2692L130.424 54.1099H128.57L126.344 58.5604L131.907 64.1236H146.743C146.743 64.1236 143.808 67.7438 142.292 70.614C141.041 72.9834 139.325 77.1044 139.325 77.1044L143.176 76.4042C145.419 75.9963 147.484 77.7198 147.484 80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71.5412H92.5943M147.484 80V80C147.484 77.7198 145.419 75.9963 143.176 76.4042L139.325 77.1044C139.325 77.1044 141.041 72.9834 142.292 70.614C143.808 67.7438 146.743 64.1236 146.743 64.1236H131.907M92.5943 71.5412H97.4157L104.833 64.1236H131.907M92.5943 71.5412L105.575 58.5604M105.575 58.5604H126.344M105.575 58.5604L104.092 54.1099H128.57L126.344 58.5604M126.344 58.5604L131.907 64.1236M111.88 51.1429V51.1429C115.331 51.1429 118.772 51.5206 122.141 52.2692L130.424 54.1099H102.608L104.092 52.9973H106.688V51.1429H107.429M111.88 51.1429L106.688 41.5H104.462L107.429 51.1429M111.88 51.1429H107.429" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var S2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 74.4634L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 85.2378L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75L66.5 74.4634Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 74.4634L71 67.6585L71 61.9878L89.5625 61.9878L89.5625 81.2683L93.5 85.2378M93.5 85.2378L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 85.2378Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M71 55.375L64.25 55.375L64.25 46.375L71 41.875L75.5 30.625L84.5 30.625L89 41.875L95.75 46.375L95.75 55.375L89 55.375L85.625 58.75L74.375 58.75L71 55.375Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M74.375 58.75L71 55.375L64.25 55.375L64.25 46.375L71 41.875L75.5 30.625M74.375 58.75L85.625 58.75M74.375 58.75L74.375 43C74.6384 38.5926 75.5 30.625 75.5 30.625M85.625 58.75L89 55.375L95.75 55.375L95.75 46.375L89 41.875L84.5 30.625M85.625 58.75L85.625 43C85.3616 38.5926 84.5 30.625 84.5 30.625M84.5 30.625L75.5 30.625" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 49.625L85.625 55.25L83.375 56.375L76.625 56.375L74.375 55.25L74.375 49.625L76.625 53L83.375 53L85.625 49.625Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 53L85.625 49.625L85.625 55.25L83.375 56.375M83.375 53L76.625 53M83.375 53L83.375 56.375M76.625 53L74.375 49.625L74.375 55.25L76.625 56.375M76.625 53L76.625 56.375M76.625 56.375L83.375 56.375" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var _2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M21.3861 87.1181H140.367C144.298 87.1181 147.485 83.9312 147.485 80C147.485 77.3161 145.721 75.4558 143.354 74.1896C142.097 73.5171 141.313 72.47 142.293 70.614C143.809 67.7438 147.485 61 147.485 61C139.641 59.2601 125.9 58.5457 110.345 58.2682V55.5604L112.57 51.1099H114.425L106.142 49.2692C102.773 48.5206 99.3318 48.1429 95.8807 48.1429L94.7268 46H102.001L104.834 43H93.0345L90.6883 38.5H88.4631L90.2323 43H74.5007V26H64.0007V71.5412H8.48505C8.48505 71.5412 7.50138 78 12.485 80L21.3861 83.0385V87.1181ZM75.8339 58.1236L74.5007 60.5354V48.1429V46H90.7708L91.4301 48.1429H89.6883L86.6883 49.9973H77.0922L75.6087 51.1099H77.0922L78.5757 55.5604V58.1199C77.6695 58.1223 76.7557 58.1236 75.8339 58.1236Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.485 80C65.2058 80 147.485 80 147.485 80M12.485 80C15.9611 81.1866 21.3861 83.0385 21.3861 83.0385M12.485 80C7.50138 78 8.48505 71.5412 8.48505 71.5412H64.0007M12.485 80L21.3861 83.0385M147.485 80V80C147.485 83.9312 144.298 87.1181 140.367 87.1181V87.1181M147.485 80V80C147.485 77.3161 145.721 75.4557 143.354 74.1896V74.1896M147.485 80C147.485 77.3161 145.721 75.4558 143.354 74.1896M147.485 80C147.485 83.9312 144.298 87.1181 140.367 87.1181M21.3861 83.0385V87.1181H140.367M147.485 61C147.485 61 143.809 67.7438 142.293 70.614C141.313 72.47 142.097 73.5171 143.354 74.1896M147.485 61C134.501 58.1199 105.36 58.0499 78.5757 58.1199M147.485 61C139.641 59.2601 125.9 58.5457 110.345 58.2682V55.5604M78.5757 55.5604H110.345M78.5757 55.5604L77.0922 51.1099M78.5757 55.5604V58.1199M110.345 55.5604L112.57 51.1099M112.57 51.1099H77.0922M112.57 51.1099H114.425M77.0922 51.1099H75.6087M75.6087 51.1099H114.425M75.6087 51.1099L77.0922 49.9973H86.6883L89.6883 48.1429H91.4301M114.425 51.1099L106.142 49.2692M95.8807 48.1429V48.1429C99.3318 48.1429 102.773 48.5206 106.142 49.2692V49.2692M95.8807 48.1429H91.4301M95.8807 48.1429L94.7268 46M95.8807 48.1429C99.3318 48.1429 102.773 48.5206 106.142 49.2692M91.4301 48.1429L90.7708 46M64.0007 71.5412V26H74.5007V43M64.0007 71.5412H68.4164L74.5007 60.5354M74.5007 46V48.1429V60.5354M74.5007 46V43M74.5007 46H90.7708M74.5007 43H90.2323M93.0345 43H104.834L102.001 46H94.7268M93.0345 43L90.6883 38.5H88.4631L90.2323 43M93.0345 43H90.2323M90.7708 46H94.7268M74.5007 60.842V60.5354M78.5757 58.1199C77.6695 58.1223 76.7557 58.1236 75.8339 58.1236L74.5007 60.5354" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var V2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 81L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 81L93.5 135.25C93.5 142.706 87.4558 148.75 80 148.75C72.5442 148.75 66.5 142.706 66.5 135.25L66.5 81Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M66.5 81L73 81L73 77.9878L87 77.9878L87 81L93.5 81M93.5 81L93.5 135.25C93.5 142.706 87.4558 148.75 80 148.75V148.75C72.5442 148.75 66.5 142.706 66.5 135.25L66.5 42.1402C66.5 9.25 80 9.25 80 9.25C80 9.25 93.5 9.25 93.5 42.1402L93.5 81Z" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74.375 80.125L71.5 84L67 84L64 80L64 65L71 59.25L75.5 46L84.5 46L89 59.25L96 65L96 80.125L93 84L88.5 84L85.625 80.125L85.625 76L74.375 76L74.375 80.125Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M84.5 46L89 59.25L96 65L96 80.125L93 84L88.5 84L85.625 80.125L85.625 76M84.5 46L75.5 46M84.5 46C84.5 46 85.3616 55.5926 85.625 60L85.625 76M75.5 46L71 59.25L64 65L64 80L67 84L71.5 84L74.375 80.125L74.375 76M75.5 46C75.5 46 74.6384 55.5926 74.375 60L74.375 76M74.375 76L85.625 76" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M85.625 65L85.625 70.625L83.375 71.75L76.625 71.75L74.375 70.625L74.375 65L76.625 68.375L83.375 68.375L85.625 65Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M83.375 68.375L85.625 65L85.625 70.625L83.375 71.75M83.375 68.375L76.625 68.375M83.375 68.375L83.375 71.75M76.625 68.375L74.375 65L74.375 70.625L76.625 71.75M76.625 68.375L76.625 71.75M76.625 71.75L83.375 71.75" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<rect x="82.4185" y="91.8209" width="5" height="31" transform="rotate(-150 82.4185 91.8209)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="79.9992" cy="91.0031" r="5.5" transform="rotate(-150 79.9992 91.0031)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var A2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var Z2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M53.0312 72H80.9609C80.4482 64.7347 74.3918 59 66.9961 59C59.6003 59 53.544 64.7347 53.0312 72ZM139.961 72C139.448 64.7347 133.392 59 125.996 59C118.6 59 112.544 64.7347 112.031 72H139.961ZM110.961 72C110.448 64.7347 104.392 59 96.9961 59C89.6003 59 83.544 64.7347 83.0312 72H110.961Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M53.0312 72L52.5325 71.9648L52.4947 72.5H53.0312V72ZM80.9609 72V72.5H81.4975L81.4597 71.9648L80.9609 72ZM139.961 72V72.5H140.497L140.46 71.9648L139.961 72ZM112.031 72L111.532 71.9648L111.495 72.5H112.031V72ZM110.961 72V72.5H111.497L111.46 71.9648L110.961 72ZM83.0312 72L82.5325 71.9648L82.4947 72.5H83.0312V72ZM53.0312 72.5H80.9609V71.5H53.0312V72.5ZM81.4597 71.9648C80.9286 64.4396 74.6562 58.5 66.9961 58.5V59.5C74.1275 59.5 79.9678 65.0299 80.4622 72.0352L81.4597 71.9648ZM66.9961 58.5C59.336 58.5 53.0636 64.4396 52.5325 71.9648L53.53 72.0352C54.0244 65.0299 59.8647 59.5 66.9961 59.5V58.5ZM140.46 71.9648C139.929 64.4396 133.656 58.5 125.996 58.5V59.5C133.127 59.5 138.968 65.0299 139.462 72.0352L140.46 71.9648ZM125.996 58.5C118.336 58.5 112.064 64.4396 111.532 71.9648L112.53 72.0352C113.024 65.0299 118.865 59.5 125.996 59.5V58.5ZM112.031 72.5H139.961V71.5H112.031V72.5ZM111.46 71.9648C110.929 64.4396 104.656 58.5 96.9961 58.5V59.5C104.127 59.5 109.968 65.0299 110.462 72.0352L111.46 71.9648ZM96.9961 58.5C89.336 58.5 83.0636 64.4396 82.5325 71.9648L83.53 72.0352C84.0244 65.0299 89.8647 59.5 96.9961 59.5V58.5ZM83.0312 72.5H110.961V71.5H83.0312V72.5Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M140.366 87.1181H21.3855V83.0385L12.4844 80V71H18.4844V63L22 44H26V63H32.4844V53.5604V50.1099L31 48.9973L32 48.1429H37.4294L37.2747 38.5H39.5L41.88 48.1429H45.8152C48.7962 48.1429 51.7388 48.8152 54.4239 50.1099H52.5695L50.3443 53.5604V71H117.416L124.833 64.1236H148C148 64.1236 148 68.5 145.5 71C143.605 72.8947 143.5 75.6209 143.5 75.6209C145.701 75.6209 147.484 77.4047 147.484 79.6053V80C147.484 83.9312 144.297 87.1181 140.366 87.1181Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80H147.484M12.4844 80L21.3855 83.0385V87.1181H140.366C144.297 87.1181 147.484 83.9312 147.484 80V80M12.4844 80V71H18.4844M147.484 80V79.6053C147.484 77.4047 145.701 75.6209 143.5 75.6209V75.6209C143.5 75.6209 143.605 72.8947 145.5 71C148 68.5 148 64.1236 148 64.1236H124.833L117.416 71H50.3443M18.4844 71H50.3443M18.4844 71V63L22 44H26V63H32.4844V53.5604M32.4844 53.5604H50.3443M32.4844 53.5604V50.1099M50.3443 53.5604L52.5695 50.1099H32.4844M50.3443 53.5604V71M32.4844 50.1099H54.4239V50.1099C51.7388 48.8152 48.7962 48.1429 45.8152 48.1429H41.88M32.4844 50.1099L31 48.9973L32 48.1429H37.4294M41.88 48.1429L39.5 38.5H37.2747L37.4294 48.1429M41.88 48.1429H37.4294" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="136" cy="70" r="2" fill="var(--instrument-tick-mark-secondary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var T2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M66.5 146.75L66.5 32.1402C66.5 11.5 80 9.25 80 9.25C80 9.25 93.5 11.5 93.5 32.1402L93.5 146.75C93.5 147.855 92.6046 148.75 91.5 148.75L90.125 148.75L69.875 148.75L68.5 148.75C67.3954 148.75 66.5 147.855 66.5 146.75Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M74 122L64 122L64 118L72 118L75 114L85 114L88 118L96 118L96 122L86 122L86 138.75L74 138.75L74 122Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="44" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="70" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<circle cx="80" cy="96" r="11.5" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var P2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M140.366 87.1182H21.3855V83.0386L12.4844 80.0001C12.4844 77.5441 14.487 75.5592 16.943 75.5812L21.3855 75.621L84.5943 75.5413L96.8333 64.1237H100.012V49.5H101H103H105.575L106.76 54.5605H115.281C122.13 54.5605 128.463 58.203 131.907 64.1237H138C141.233 66.387 144.251 70.5308 145.98 73.1767C147.01 74.7539 147.484 76.6105 147.484 78.4946V80.0001C147.484 83.9313 144.297 87.1182 140.366 87.1182Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80.0001H147.484M12.4844 80.0001L21.3855 83.0386V87.1182H140.366C144.297 87.1182 147.484 83.9313 147.484 80.0001V80.0001M12.4844 80.0001V80.0001C12.4844 77.5441 14.487 75.5592 16.943 75.5812L21.3855 75.621L84.5943 75.5413L96.8333 64.1237H100.012M147.484 80.0001V78.4946C147.484 76.6105 147.01 74.7539 145.98 73.1767C144.251 70.5308 141.233 66.387 138 64.1237H131.907M106.76 54.5605H115.281C122.13 54.5605 128.463 58.203 131.907 64.1237V64.1237M131.907 64.1237H109M100.012 64.1237V49.5H101M100.012 64.1237H109M109 64.1237L105.575 49.5H103M101 49.5V45M101 49.5H103M103 49.5V47" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var z2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M147.484 80.0001L146.814 81.5981C145.412 84.9422 142.14 87.1182 138.514 87.1182H21.3855V83.0386L12.4844 80.0001C12.4844 77.5376 14.4806 75.5413 16.9432 75.5413H21L30.5 56.5H32H34.5H36.5L33.5 75.5413H36.5943L48.8333 64.1237H100.012H127.5L145.461 66.8188C147.93 67.1894 149.587 69.5517 149.094 72L147.484 80.0001Z" fill="var(--instrument-frame-primary-color)"/>
<path d="M12.4844 80.0001L21.3855 83.0386V87.1182H138.514C142.14 87.1182 145.412 84.9422 146.814 81.5981L147.484 80.0001L149.094 72M12.4844 80.0001V80.0001C12.4844 77.5376 14.4806 75.5413 16.9432 75.5413H21M12.4844 80.0001H107.04C116.302 80.0001 125.519 78.7134 134.427 76.1768L149.094 72M21 75.5413L30.5 56.5H32M21 75.5413H33.5M33.5 75.5413H36.5943L48.8333 64.1237H100.012H127.5L145.461 66.8188C147.93 67.1894 149.587 69.5517 149.094 72V72M33.5 75.5413L36.5 56.5H34.5M34.5 56.5V48.5M34.5 56.5H32M32 56.5V53" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var B2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var O2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var D2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var E2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var R2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var I2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
<ellipse cx="80" cy="61" rx="4" ry="4" transform="rotate(90 80 61)" fill="var(--instrument-tick-mark-secondary-color)"/>
<path d="M86 60C87.1046 60 88 60.8954 88 62L88 86C88 87.1046 87.1046 88 86 88L74 88C72.8954 88 72 87.1046 72 86L72 62C72 60.8954 72.8954 60 74 60L86 60Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path d="M113.61 46.5204C113.678 46.429 113.565 46.3127 113.472 46.3788L92.0296 61.7523C89.9911 63.2139 87.5458 63.9999 85.0374 63.9999H73.9992C71.4028 63.9999 68.8764 63.1578 66.7993 61.6L46.5198 46.3906C46.4283 46.3221 46.3126 46.4353 46.3791 46.5283L61.7526 67.9705C63.2142 70.0091 64.0002 72.4544 64.0002 74.9627V85.0371C64.0002 87.5455 63.2142 89.9908 61.7526 92.0293L46.3791 113.472C46.3125 113.565 46.4283 113.679 46.5198 113.61L66.8002 98.3999C68.8774 96.8421 71.4038 95.9999 74.0002 95.9999H85.0373C87.5457 95.9999 89.9911 96.786 92.0297 98.2477L113.472 113.622C113.565 113.688 113.678 113.572 113.61 113.48L98.4002 93.2009C96.8423 91.1237 96.0002 88.5974 96.0002 86.001V73.999C96.0002 71.4025 96.8424 68.8761 98.4003 66.7989L113.61 46.5204Z" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" stroke="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M45.6232 41C44.5326 41 43.5232 41.3497 42.7013 41.9424L42.3039 41.5957C41.8708 41.2171 41.2951 41.0437 40.7248 41.1191L24.0129 43.334C23.2505 43.4352 22.613 43.9652 22.3742 44.6963L22.05 45.6895C21.8392 46.3356 22.3215 46.9997 23.0011 47H40.7238C41.1872 49.2821 43.2043 51 45.6232 51C46.7144 50.9999 47.7231 50.649 48.5451 50.0557L48.9406 50.4033C49.3738 50.7823 49.9501 50.9564 50.5207 50.8809L67.2316 48.665C67.9941 48.5639 68.6315 48.0339 68.8703 47.3027L69.1945 46.3096C69.4051 45.6635 68.9238 45.0004 68.2443 45H50.5226C50.0594 42.718 48.0419 41.0003 45.6232 41ZM43.8927 47C44.2387 47.5972 44.8834 48 45.6232 48C45.795 47.9999 45.9612 47.9754 46.1203 47.9346L47.7677 49.375C47.1479 49.7698 46.4126 49.9999 45.6232 50C43.7593 50 42.1922 48.7253 41.7482 47H43.8927ZM45.6232 42C47.4868 42.0003 49.0533 43.2749 49.4972 45H47.3527C47.0068 44.403 46.3628 44.0002 45.6232 44C45.4516 44 45.2851 44.0238 45.1261 44.0645L43.4797 42.623C44.0992 42.2291 44.8346 42 45.6232 42Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M40.1992 91.1499C39.5205 91.1136 39.0039 91.7511 39.1797 92.4077L43.7666 109.526C41.6821 110.564 40.545 112.957 41.1709 115.293C41.4534 116.348 42.0529 117.232 42.8389 117.873L42.6055 118.344C42.3516 118.861 42.3331 119.462 42.5537 119.994L49.0185 135.562C49.3136 136.272 49.9907 136.751 50.7588 136.792L51.8017 136.848C52.4803 136.884 52.9969 136.248 52.8213 135.591L48.2344 118.473C50.3187 117.435 51.4559 115.042 50.8301 112.706C50.5478 111.652 49.9491 110.768 49.1641 110.127L49.3955 109.654C49.6491 109.137 49.6678 108.537 49.4473 108.005L42.9824 92.4361C42.6873 91.7258 42.0101 91.247 41.2422 91.2056L40.1992 91.1499ZM48.708 111.056C49.2486 111.553 49.6602 112.203 49.8642 112.964C50.3464 114.765 49.5201 116.608 47.9687 117.483L47.4141 115.412C47.9013 114.923 48.123 114.196 47.9316 113.482C47.8872 113.316 47.8217 113.161 47.7412 113.018L48.708 111.056ZM44.5859 112.586C44.0986 113.075 43.877 113.802 44.0683 114.517C44.1129 114.683 44.18 114.838 44.2607 114.981L43.2949 116.944C42.7534 116.447 42.341 115.797 42.1367 115.035C41.6545 113.235 42.4799 111.392 44.0312 110.516L44.5859 112.586Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M96.6179 32.8858C95.9071 32.5923 95.0906 32.7324 94.5183 33.2461L93.7409 33.9444C93.2354 34.3986 93.3203 35.2148 93.9089 35.5547L109.257 44.4151C108.517 46.6231 109.405 49.1196 111.5 50.3291C112.445 50.8748 113.494 51.0755 114.503 50.9727L114.672 51.4717C114.857 52.0166 115.269 52.455 115.801 52.6748L131.382 59.1114C132.092 59.405 132.909 59.2648 133.481 58.751L134.26 58.0528C134.764 57.5984 134.679 56.7843 134.091 56.4444L118.743 47.583C119.483 45.375 118.594 42.8785 116.5 41.669C115.555 41.1238 114.507 40.9221 113.499 41.0244L113.328 40.5254C113.142 39.981 112.731 39.5431 112.199 39.3233L96.6179 32.8858ZM112.001 46C112.002 46.6902 112.359 47.3615 113 47.7315C113.149 47.8175 113.305 47.8796 113.464 47.9239L114.17 49.9942C113.435 50.026 112.683 49.8576 112 49.4629C110.386 48.531 109.666 46.6438 110.144 44.9278L112.001 46ZM113.833 42.003C114.566 41.9716 115.317 42.141 116 42.5352C117.614 43.4671 118.332 45.3543 117.854 47.0703L115.998 45.9981C115.997 45.3079 115.64 44.6366 115 44.2666C114.851 44.1808 114.695 44.1185 114.537 44.0743L113.833 42.003Z" fill="var(--instrument-tick-mark-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M134.569 102.481C134.429 101.816 133.68 101.482 133.091 101.822L117.743 110.683C116.201 108.938 113.595 108.459 111.5 109.668C110.555 110.214 109.856 111.022 109.441 111.947L108.925 111.844C108.36 111.732 107.774 111.87 107.318 112.221L93.9533 122.495C93.3435 122.964 93.0562 123.741 93.215 124.494L93.4308 125.516C93.5715 126.181 94.3207 126.515 94.9093 126.176L110.257 117.314C111.799 119.059 114.405 119.537 116.5 118.328C117.444 117.783 118.143 116.976 118.559 116.052L119.076 116.153C119.641 116.265 120.226 116.127 120.682 115.776L134.047 105.503C134.657 105.034 134.944 104.255 134.785 103.503L134.569 102.481ZM117.544 115.851C117.205 116.502 116.683 117.069 116 117.463C114.386 118.395 112.392 118.074 111.145 116.802L113.001 115.729C113.599 116.074 114.359 116.1 115 115.73C115.149 115.644 115.281 115.54 115.399 115.426L117.544 115.851ZM112 110.534C113.614 109.602 115.608 109.923 116.856 111.195L114.999 112.267C114.401 111.923 113.641 111.897 113 112.266C112.851 112.353 112.719 112.457 112.602 112.572L110.455 112.147C110.795 111.496 111.317 110.929 112 110.534Z" fill="var(--instrument-tick-mark-secondary-color)"/>
</svg>
`;var N2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var j2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var F2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var U2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var W2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var G2=c`<svg width="160" height="160" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`;var Dr=(e=>{e["none"]="none";e["small"]="small";e["medium"]="medium";e["large"]="large";return e})(Dr||{});var Er=(e=>{e["carFerryAft"]="car-ferry-aft";e["carFerrySide"]="car-ferry-side";e["carFerryTop"]="car-ferry-top";e["cargoFore"]="cargo-fore";e["cargoSide"]="cargo-side";e["cargoTop"]="cargo-top";e["cargoWindFore"]="cargo-wind-fore";e["cargoWindSide"]="cargo-wind-side";e["cargoWindTop"]="cargo-wind-top";e["fishingVesselSide"]="fishing-vessel-side";e["fishingVesselTop"]="fishing-vessel-top";e["foreFore"]="fore-fore";e["genericSide"]="generic-side";e["genericTop"]="generic-top";e["psvAft"]="psv-aft";e["psvFore"]="psv-fore";e["psvSide"]="psv-side";e["psvTop"]="psv-top";e["sovSide"]="sov-side";e["sovTop"]="sov-top";e["tankerFore"]="tanker-fore";e["tankerSide"]="tanker-side";e["tankerTop"]="tanker-top";e["usvLargeSide"]="usv-large-side";e["usvSmallSide"]="usv-small-side";e["droneMediumFront"]="drone-medium-front";e["droneMediumStbdSide"]="drone-medium-stbd-side";e["droneMediumTop"]="drone-medium-top";e["droneSmallFront"]="drone-small-front";e["droneSmallStbdSide"]="drone-small-stbd-side";e["droneSmallTop"]="drone-small-top";e["droneGenericFront"]="drone-generic-front";e["droneGenericSide"]="drone-generic-side";e["droneGenericTop"]="drone-generic-top";e["rovFront"]="rov-front";e["rovSide"]="rov-side";e["rovTop"]="rov-top";return e})(Er||{});var ca={["car-ferry-aft"]:p2,["car-ferry-side"]:h2,["car-ferry-top"]:u2,["cargo-fore"]:f2,["cargo-side"]:v2,["cargo-top"]:m2,["cargo-wind-fore"]:g2,["cargo-wind-side"]:b2,["cargo-wind-top"]:y2,["fishing-vessel-side"]:w2,["fishing-vessel-top"]:C2,["fore-fore"]:k2,["generic-side"]:L2,["generic-top"]:x2,["psv-aft"]:$2,["psv-fore"]:M2,["psv-side"]:H2,["psv-top"]:S2,["sov-side"]:_2,["sov-top"]:V2,["tanker-fore"]:A2,["tanker-side"]:Z2,["tanker-top"]:T2,["usv-large-side"]:P2,["usv-small-side"]:z2,["drone-medium-front"]:B2,["drone-medium-stbd-side"]:O2,["drone-medium-top"]:D2,["drone-small-front"]:E2,["drone-small-stbd-side"]:R2,["drone-small-top"]:I2,["drone-generic-front"]:N2,["drone-generic-side"]:j2,["drone-generic-top"]:F2,["rov-front"]:U2,["rov-side"]:W2,["rov-top"]:G2};var q2="important";var Ou=" !"+q2;var da=wo(class extends to{constructor(e){if(super(e),e.type!==Eo.ATTRIBUTE||"style"!==e.name||e.strings?.length>2)throw Error("The `styleMap` directive must be used in the `style` attribute and must be the only part in the attribute.")}render(e){return Object.keys(e).reduce((t,i)=>{const o=e[i];return null==o?t:t+`${i=i.includes("-")?i:i.replace(/(?:^(webkit|moz|ms|o)|)(?=[A-Z])/g,"-$&").toLowerCase()}:${o};`},"")}update(e,[t]){const{style:i}=e.element;if(void 0===this.ft)return this.ft=new Set(Object.keys(t)),this.render(t);for(const o of this.ft)null==t[o]&&(this.ft.delete(o),o.includes("-")?i.removeProperty(o):i[o]=null);for(const o in t){const r=t[o];if(null!=r){this.ft.add(o);const a="string"==typeof r&&r.endsWith(Ou);o.includes("-")||a?i.setProperty(o,a?r.slice(0,-11):r,a?q2:""):i[o]=r}}return ar}});function Y2(e){return K2({filename:`wind-${e.wind+1}.svg`,fromDirectionDeg:e.fromDirectionDeg,radius:e.radius,color:e.color})}function Q2(e){return K2({filename:`current-${e.current}.svg`,fromDirectionDeg:e.fromDirectionDeg,radius:e.radius,color:e.color})}function K2(e){const{filename:t,fromDirectionDeg:i,radius:o,color:r}=e;const a=(i-180)*Math.PI/180;const n=Du[t];const p=r?{"--instrument-regular-secondary-color":r}:{};return c`<g style=${da(p)} transform="translate(${-Math.sin(a)*o} ${Math.cos(a)*o}) rotate(${180+i}) translate(-24, 0) scale(2)">
    ${n}
  </g>`}var Du={"current-0.svg":c`<path d="M11 2V22H13V2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 2V22H13V2Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-1.svg":c`<path d="M11 7.00002L11 24L13 24L13 7.00005L11 7.00002Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79309 5.20723L12.0002 0.00012207L17.2073 5.20723L15.7931 6.62144L12.0002 2.82855L8.2073 6.62144L6.79309 5.20723Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 7.00002L11 24L13 24L13 7.00005L11 7.00002Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79309 5.20723L12.0002 0.00012207L17.2073 5.20723L15.7931 6.62144L12.0002 2.82855L8.2073 6.62144L6.79309 5.20723Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-2.svg":c`<path d="M10.9742 12.0003L10.9742 24.0049L12.9999 24.005L12.9999 12.0004L10.9742 12.0003Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79285 5.20747L12 0.000366211L17.2071 5.20747L15.7928 6.62169L12 2.82879L8.20706 6.62169L6.79285 5.20747Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99988 10.5861L12.207 5.37903L17.4141 10.5861L15.9999 12.0003L12.207 8.20745L8.41409 12.0003L6.99988 10.5861Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M10.9742 12.0003L10.9742 24.0049L12.9999 24.005L12.9999 12.0004L10.9742 12.0003Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79285 5.20747L12 0.000366211L17.2071 5.20747L15.7928 6.62169L12 2.82879L8.20706 6.62169L6.79285 5.20747Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.99988 10.5861L12.207 5.37903L17.4141 10.5861L15.9999 12.0003L12.207 8.20745L8.41409 12.0003L6.99988 10.5861Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-3.svg":c`<path d="M11 18L11 24L13 24L13 18L11 18Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 18L11 24L13 24L13 18L11 18Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" fill="var(--instrument-regular-secondary-color)"/>`,"current-4.svg":c`<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 22.5858L12.2071 17.3787L17.4142 22.5858L16 24L12.2071 20.2071L8.41421 24L7 22.5858Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.79297 5.20711L12.0001 0L17.2072 5.20711L15.793 6.62132L12.0001 2.82843L8.20718 6.62132L6.79297 5.20711Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 10.5858L12.2071 5.37866L17.4142 10.5858L16 12L12.2071 8.20709L8.41421 12L7 10.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 16.5858L12.2071 11.3787L17.4142 16.5858L16 18L12.2071 14.2071L8.41421 18L7 16.5858Z" fill="var(--instrument-regular-secondary-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7 22.5858L12.2071 17.3787L17.4142 22.5858L16 24L12.2071 20.2071L8.41421 24L7 22.5858Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-1.svg":c`<path d="M12 2C6.47715 2 2 6.47715 2 12H3.90476C3.90476 7.52912 7.52912 3.90476 12 3.90476V2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M22 12C22 6.47715 17.5228 2 12 2V3.90476C16.4709 3.90476 20.0952 7.52912 20.0952 12H22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M12 22C17.5228 22 22 17.5228 22 12H20.0952C20.0952 16.4709 16.4709 20.0952 12 20.0952V22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M2 12C2 17.5228 6.47715 22 12 22V20.0952C7.52912 20.0952 3.90476 16.4709 3.90476 12H2Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M12 2C6.47715 2 2 6.47715 2 12H3.90476C3.90476 7.52912 7.52912 3.90476 12 3.90476V2Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M22 12C22 6.47715 17.5228 2 12 2V3.90476C16.4709 3.90476 20.0952 7.52912 20.0952 12H22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M12 22C17.5228 22 22 17.5228 22 12H20.0952C20.0952 16.4709 16.4709 20.0952 12 20.0952V22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M2 12C2 17.5228 6.47715 22 12 22V20.0952C7.52912 20.0952 3.90476 16.4709 3.90476 12H2Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-2.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-3.svg":c`<path d="M11 24L13 24L13 7L15 7L12 -1.74846e-07L9 7L11 7L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 21L8 19L11 19L11 21L8 21Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24L13 24L13 7L15 7L12 -1.74846e-07L9 7L11 7L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 21L8 19L11 19L11 21L8 21Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-4.svg":c`<path d="M11 24L13 24L13 7L15 7L12 -2.62268e-07L9 7L11 7L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M6 24L6 22L11 22L11 24L6 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24L13 24L13 7L15 7L12 -2.62268e-07L9 7L11 7L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M6 24L6 22L11 22L11 24L6 24Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-5.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 21L8 19H12V21H8Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 21L8 19H12V21H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-6.svg":c`<path d="M11 24H13L13 7L15 7L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7L15 7L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-7.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 18L8 16H12V18H8Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 18L8 16H12V18H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-8.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-9.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 24L5 22H12V24H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 21L5 19H12V21H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M8 15L8 13H12V15H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 24L5 22H12V24H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 21L5 19H12V21H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M8 15L8 13H12V15H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-10.svg":c`<path d="M11 24H13L13 7H15L12 0L9 7H11L11 24Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
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
<path d="M8 12L8 10H12V12H8Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-11.svg":c`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 20L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 20L5 22Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-12.svg":c`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>`,"wind-13.svg":c`<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 18L5 16H12V18H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 15L5 13H12V15H5Z" stroke="var(--border-silhouette-color)" stroke-width="2"/>
<path d="M5 22L13 24L13 7H15L12 0L9 7H11L11 19L5 22Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 18L5 16H12V18H5Z" fill="var(--instrument-regular-secondary-color)"/>
<path d="M5 15L5 13H12V15H5Z" fill="var(--instrument-regular-secondary-color)"/>`};function ml(e){const{areas:t,outerRadius:i,innerRadius:o,extension:r,targetSize:a,margin:n=.06}=e;if(t.length===0){const Y=a;return{radiusOffset:0,x:-Y/2,y:-Y/2,width:Y,height:Y,viewBox:`${-Y/2} ${-Y/2} ${Y} ${Y}`}}const p=a*(1-2*n);const d=Y=>{const R=X2(t,i+Y,o+Y,r);return Math.max(R.xMax-R.xMin,R.yMax-R.yMin)};let f=0;let g=a;for(let Y=0;Y<16&&d(g)<p;Y++){g*=2}for(let Y=0;Y<50;Y++){const R=(f+g)/2;const B=d(R);if(B<p){f=R}else{g=R}}const m=Math.max(0,f);const u=X2(t,i+m,o+m,r);const M=u.xMax-u.xMin;const C=u.yMax-u.yMin;const A=Math.max(M,C);const H=A*(1+n*2);const _=(u.xMin+u.xMax)/2;const S=(u.yMin+u.yMax)/2;const E=vl(_-H/2);const D=vl(S-H/2);const K=vl(H);const I=vl(H);return{radiusOffset:m,x:E,y:D,width:K,height:I,viewBox:`${E} ${D} ${K} ${I}`}}function X2(e,t,i,o){const r=t+o;const a=i;let n=Infinity;let p=-Infinity;let d=Infinity;let f=-Infinity;const g=(m,u)=>{if(m<n)n=m;if(m>p)p=m;if(u<d)d=u;if(u>f)f=u};for(const m of e){const u=m.startAngle*Math.PI/180;const M=m.endAngle*Math.PI/180;for(const _ of[r,a]){g(_*Math.sin(u),-_*Math.cos(u));g(_*Math.sin(M),-_*Math.cos(M))}const C=(m.startAngle%360+360)%360;const A=(m.endAngle%360+360)%360;const H=[0,90,180,270];for(const _ of H){if(Eu(C,A,_)){const S=_*Math.PI/180;for(const E of[r,a]){g(E*Math.sin(S),-E*Math.cos(S))}}}}if(n===Infinity){return{xMin:0,xMax:0,yMin:0,yMax:0}}return{xMin:n,xMax:p,yMin:d,yMax:f}}function Eu(e,t,i){const o=(e%360+360)%360;const r=(t%360+360)%360;const a=(i%360+360)%360;if(o<=r){return a>=o&&a<=r}return a>=o||a<=r}function vl(e){return Math.round(e*1e4)/1e4}var Ru=Object.defineProperty;var Iu=Object.getOwnPropertyDescriptor;var ve=(e,t,i,o)=>{var r=o>1?void 0:o?Iu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Ru(t,i,r);return r};var Lr=(e=>{e["single"]="single";e["double"]="double";e["doubleThin"]="doubleThin";e["triple"]="triple";return e})(Lr||{});var qt=368/2;var Xa=320/2;var gl=224/2;var ep=272/2;var tp=176/2;function w1(e){switch(e){case"single":return Xa;case"double":return gl;case"doubleThin":return ep;case"triple":return tp;default:throw new Error(`Unknown WatchCircleType: ${e}`)}}var J2=4;var pe=class extends k{constructor(){super(...arguments);this._setpointId=`watch-setpoint-${Math.random().toString(36).slice(2,9)}`;this._newSetpointId=`watch-new-setpoint-${Math.random().toString(36).slice(2,9)}`;this.state=Le.active;this.priority=me.regular;this.watchCircleType="single";this.northArrow=false;this.atAngleSetpoint=false;this.angleSetpointAtZeroDeadband=.5;this.setpointOverride=false;this.touching=false;this.animateSetpoint=false;this._setpointCssAngle=0;this._setpointCssAngleInit=false;this.areas=[];this.barAreas=[];this.needles=[];this.tickmarks=[];this.tickmarksInside=false;this.tickmarkStyle=He.regular;this.advices=[];this.crosshairEnabled=false;this.showLabels=false;this.vessels=[];this.wind=null;this.windFromDirectionDeg=null;this.windSymbolRadius=null;this.current=null;this.currentFromDirectionDeg=null;this.currentSymbolRadius=null;this.starboardPortIndicator=false;this.clipTop=0;this.clipBottom=0;this.scaleWindIcon=1;this.zoomToFitArc=false;this.tickFadeAngle=0;this.rotPosition=Ya.innerCircle;this.rotStartAngle=0;this.rotEndAngle=0;this.rotPortStarboard=false;this.rotAtZeroDeadband=Qa;this._rotationsPerMinute=0;this._resizeController=new Lo(this,{});this._rOff=0}set rotationsPerMinute(e){this._rotationsPerMinute=e;if(this._rotController){this._rotController.rotationsPerMinute=e}}get rotationsPerMinute(){return this._rotationsPerMinute}willUpdate(e){super.willUpdate(e);if(e.has("newAngleSetpoint")&&this.animateSetpoint){const t=e.get("newAngleSetpoint");if(t!==void 0&&this.newAngleSetpoint===void 0){this._departingNewAngleSetpoint=t;clearTimeout(this._animationTimer);const i=cl(this);this._animationTimer=setTimeout(()=>{this._departingNewAngleSetpoint=void 0},i)}}}disconnectedCallback(){super.disconnectedCallback();clearTimeout(this._animationTimer);this._rotController=fl(this,this._rotController)}updated(e){super.updated(e);const t=this.rotType?this.renderRoot.querySelector("#rot-spinner"):null;if(!t){this._rotController=fl(this,this._rotController);return}if(!this._rotController||this._rotController.el!==t){this._rotController=fl(this,this._rotController);this._rotController=new ul(this,t,this._rotationsPerMinute)}}get innerRingRadius(){return w1(this.watchCircleType)}watchCircle(){const e=[];if(this.state!==Le.off){e.push(c`
        <circle
          cx="0"
          cy="0"
          r="${172+this._rOff}"
          stroke="var(--instrument-frame-primary-color)"
          fill="none"
          stroke-width="24"
        />`);if(this.watchCircleType!=="single"){const o=Xa+this._rOff;const r=(this.watchCircleType==="doubleThin"?ep:gl)+this._rOff;const a=(o+r)/2;const n=o-r;e.push(c`
            <circle cx="0" cy="0" r=${a} stroke="var(--instrument-frame-secondary-color)" stroke-width=${n} fill="none" />
            <circle cx="0" cy="0" r=${o} stroke="var(--instrument-frame-secondary-color)" stroke-width="1" fill="none" vector-effect="non-scaling-stroke" />
            <circle cx="0" cy="0" r=${r} stroke="var(--instrument-frame-secondary-color)" stroke-width="1" fill="none" vector-effect="non-scaling-stroke" />
        `)}if(this.watchCircleType==="triple"){const o=gl+this._rOff;const r=tp+this._rOff;const a=(o+r)/2;const n=o-r;e.push(c`<circle cx="0" cy="0" r=${a} stroke="var(--instrument-frame-primary-color)" stroke-width=${n} fill="none" />`)}}const t=Math.max(200,qt+this._rOff+50);let i=e;if(this.areas.length>0){const o=this.areas.map(n=>{const p=Ga({startAngle:n.startAngle,endAngle:n.endAngle,R:qt+this._rOff,r:this.innerRingRadius+this._rOff,roundOutsideCut:n.roundOutsideCut,roundInsideCut:n.roundInsideCut});return p});const r=c`<mask id="cutMask">
        <rect x="${-t}" y="${-t}" width="${t*2}" height="${t*2}" fill="black" />
        ${o.map(n=>c`<path d=${n} fill="white" vector-effect="non-scaling-stroke" stroke="white" stroke-width="1"/>`)}
      </mask>`;const a=c`<clipPath id="rot-arc-clip">${this.areas.map(n=>c`<path d=${Ga({startAngle:n.startAngle,endAngle:n.endAngle,R:qt+this._rOff+20,r:0,roundOutsideCut:n.roundOutsideCut,roundInsideCut:n.roundInsideCut})} />`)}</clipPath>`;i=[r,a,c`<g mask="url(#cutMask)">${e}</g>`];o.forEach(n=>{i.push(c`<path d=${n} fill="none" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>`)})}else{if(this.state!==Le.off){i.push(ll("outerRing",{radius:qt+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"}));i.push(c`
          ${ll("innerRing",{radius:this.innerRingRadius+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"})}
        `)}else{i.push(c`
          ${ll("innerRing",{radius:qt+this._rOff,strokeWidth:1,strokeColor:"var(--instrument-frame-tertiary-color)",strokePosition:"center",fillColor:"none"})}
        `)}}return i}_renderTickFadeDefs(){if(this.tickFadeAngle<=0||this.areas.length===0)return w;const e=this.areas[0];const t=e.endAngle-e.startAngle;const i=Math.min(this.tickFadeAngle,t/4);if(i<.5)return w;const{startAngle:o,endAngle:r}=e;const a=qt+this._rOff+200;const n=M=>M*Math.PI/180;const p=M=>a*Math.sin(n(M));const d=M=>-a*Math.cos(n(M));const f=(M,C)=>{const A=p(M),H=d(M);const _=p(C),S=d(C);const E=C-M>180?1:0;return`M 0 0 L ${A} ${H} A ${a} ${a} 0 ${E} 1 ${_} ${S} Z`};const g=(qt+this.innerRingRadius)/2+this._rOff;const m=M=>g*Math.sin(n(M));const u=M=>-g*Math.cos(n(M));return c`
      <defs>
        <linearGradient id="tickFadeL" gradientUnits="userSpaceOnUse"
          x1="${m(o)}" y1="${u(o)}"
          x2="${m(o+i)}" y2="${u(o+i)}">
          <stop offset="0" stop-color="black" />
          <stop offset="1" stop-color="white" />
        </linearGradient>
        <linearGradient id="tickFadeR" gradientUnits="userSpaceOnUse"
          x1="${m(r-i)}" y1="${u(r-i)}"
          x2="${m(r)}" y2="${u(r)}">
          <stop offset="0" stop-color="white" />
          <stop offset="1" stop-color="black" />
        </linearGradient>
        <mask id="tickFadeMask" maskUnits="userSpaceOnUse"
          x="${-a}" y="${-a}" width="${a*2}" height="${a*2}">
          <path d="${f(o+i,r-i)}" fill="white" />
          <path d="${f(o,o+i)}" fill="url(#tickFadeL)" />
          <path d="${f(r-i,r)}" fill="url(#tickFadeR)" />
        </mask>
      </defs>
    `}renderCrosshair(e,t){const i=t&&t.positions.length>0;const o=i?Math.max(...t.positions.map(a=>Math.abs(a.x!==0?a.x:a.y))):0;const r=i?3/t.scale:0;return c`
      ${i?c`
        <defs>
          <mask
            id="crosshair-label-mask"
            maskUnits="userSpaceOnUse"
            x="-${e}" y="-${e}"
            width="${e*2}" height="${e*2}"
          >
            <rect x="-${e}" y="-${e}" width="${e*2}" height="${e*2}" fill="white"/>
            <!-- Annular ring knockout: hide crosshair between labels and inner ring -->
            <circle cx="0" cy="0" r="${t.innerRingRadius}" fill="black"/>
            <circle cx="0" cy="0" r="${o-r}" fill="white"/>
            <!-- Per-label rectangular knockouts -->
            ${t.positions.map(a=>{const n=12/t.scale;const p=3/t.scale;const d=n+p*2;return c`
                <rect
                  x="${a.x-d/2}" y="${a.y-d/2}"
                  width="${d}" height="${d}"
                  fill="black"
                  transform="rotate(${-(t.rotation??0)})"
                  transform-origin="${a.x} ${a.y}"
                />
              `})}
          </mask>
        </defs>`:w}
      <g mask=${i?"url(#crosshair-label-mask)":w}>
        <line
          x1="-${e}"
          y1="0"
          x2="${e}"
          y2="0"
          stroke="var(--instrument-frame-tertiary-color)"
          stroke-width="1"
          vector-effect="non-scaling-stroke"
        />
        <line
          x1="0"
          y1="-${e}"
          x2="0"
          y2="${e}"
          stroke="var(--instrument-frame-tertiary-color)"
          stroke-width="1"
          vector-effect="non-scaling-stroke"
        />
      </g>
    `}renderBars(){if(this.barAreas.length===0){return w}return this.barAreas.map((e,t)=>{const i=Math.min(e.startAngle,e.endAngle);const o=Math.max(e.startAngle,e.endAngle);const r=Ga({r:gl+this._rOff,R:Xa+this._rOff,startAngle:i,endAngle:o,roundInsideCut:false,roundOutsideCut:false});const a=Xa+this._rOff+40;const n=c`<mask id="barMask-${t}">
        <rect x="${-a}" y="${-a}" width="${a*2}" height="${a*2}" fill="black" />
        <path d=${Ga({r:1,R:a,startAngle:i,endAngle:o,roundInsideCut:false,roundOutsideCut:false})} fill="white" />
      </mask>`;return c`
        ${n}
        <g mask="url(#cutMask)">
        <path 
          d=${r} 
          fill=${e.fillColor} 
          stroke=${e.fillColor} 
          stroke-width="1" 
          vector-effect="non-scaling-stroke" 
          mask="url(#barMask-${t})" 
          />
          </g>
          `})}renderNeedles(){if(this.needles.length===0){return w}return this.needles.map(e=>{return c`
        <rect 
          transform="rotate(${e.angle})" 
          x="-4" y="${-(Xa+this._rOff)}" width="8" height="48" rx="4" 
          fill=${e.fillColor} 
          stroke=${e.strokeColor}
          stroke-width="1"
          vector-effect="non-scaling-stroke"
          paint-order="stroke fill"
        />
      `})}getScale({width:e,height:t}){let i=this.clientWidth;let o=this.clientHeight;if(i===0||o===0){const a=this.parentElement?.getBoundingClientRect();if(a){i=a.width;o=a.height}}const r=Math.min(i/e,o/t);if(r===Infinity||r<0){throw new Error("Watch scale is not valid")}return r}getPadding(){if(this.padding!==void 0){return this.padding}const e=this.tickmarks.length>0&&this.tickmarks.some(t=>t.text!==void 0);if(e&&!this.tickmarksInside){return 24*2.5}return 24}render(){let e;let t;let i;if(this.arcFrame){this._rOff=this.arcFrame.radiusOffset;e=this.arcFrame.width;t=this.arcFrame.height;i=this.arcFrame.viewBox}else if(this.zoomToFitArc&&this.areas.length>0){const _=this.getPadding();const S=(176+_)*2;const E=ml({areas:this.areas,outerRadius:qt,innerRadius:this.innerRingRadius,extension:_,targetSize:S});this._rOff=E.radiusOffset;e=E.width;t=E.height;i=E.viewBox}else{this._rOff=0;e=(176+this.getPadding())*2;t=e*(1-this.clipTop/100-this.clipBottom/100);const _=-e/2+e*this.clipTop/100;i=`-${e/2} ${_} ${e} ${t}`}const o=this._rOff;const r=this.getScale({width:e,height:t});const a=this.renderSetpoint();const n=(this.tickmarksInside?this.innerRingRadius:qt)+o;const p=Math.max(...this.tickmarks.map(_=>_.text?.length??0));const d=this.tickmarks.map(_=>yi(_.angle,{size:_.type,style:this.tickmarkStyle,scale:r,text:this.showLabels?void 0:_.text,inside:this.tickmarksInside,textRadius:n,rotation:this.rotation,maxDigits:p,color:_.color,radiusOffset:o}));const f=this.advices?this.advices.map(_=>r2(_,o)):w;const g=this.tickmarksInside&&this.showLabels;const m=!this.northArrow;const u=this.showLabels?y1({scale:r,inside:this.tickmarksInside,innerRadius:this.innerRingRadius+o,includeNorth:m}):void 0;const M=u?c2({scale:r,rotation:this.rotation,inside:this.tickmarksInside,innerRadius:this.innerRingRadius+o,includeNorth:m}):w;const C=this.northArrow?d2({scale:r,rotation:this.rotation,inside:this.northArrowInside??this.tickmarksInside}):w;const A=this.wind!=null&&this.windFromDirectionDeg!=null?c`<g transform="scale(${this.scaleWindIcon})">${Y2({wind:this.wind,fromDirectionDeg:this.windFromDirectionDeg,radius:this.windSymbolRadius??192,color:this.windColor})}</g>`:w;const H=this.current!=null&&this.currentFromDirectionDeg!=null?Q2({current:this.current,fromDirectionDeg:this.currentFromDirectionDeg,radius:this.currentSymbolRadius??192,color:this.currentColor}):w;return h`
      <svg
        width="100%"
        height="100%"
        viewBox=${i}
        style="--scale: ${r}"
        transform="rotate(${this.rotation??0})"
      >
        ${this.watchCircle()} ${this.renderBars()}
        ${this.crosshairEnabled?this.renderCrosshair(qt+o,g&&u?{positions:u,rotation:this.rotation,scale:r,innerRingRadius:this.innerRingRadius+o}:void 0):w}
        ${C} ${this.renderStarboardPortIndicator()} ${H}
        ${this._renderTickFadeDefs()} ${A}
        ${this.tickFadeAngle>0&&this.areas.length>0?c`<g mask="url(#tickFadeMask)">${d}</g>`:d}
        ${this.areas.length>0?c`<g clip-path="url(#rot-arc-clip)">${this.renderRot()}</g>`:this.renderRot()}
        ${f} ${a}
        ${this.tickFadeAngle>0&&this.areas.length>0?c`<g mask="url(#tickFadeMask)">${M}</g>`:M}
        ${this.renderVesselImage()} ${this.renderNeedles()}
      </svg>
    `}getRotColors(){const e=this.rotPriority??this.priority;const t=e===me.enhanced;if(this.rotPortStarboard){let i;if(this.rotType===sa.bar){const o=((this.rotEndAngle-this.rotStartAngle)%360+360)%360;i=o<=180?o:o-360}else{i=this._rotationsPerMinute}if(i>0){return{dotColor:"var(--instrument-starboard-secondary-color)",barBgColor:"var(--instrument-starboard-primary-color)"}}if(i<0){return{dotColor:"var(--instrument-port-secondary-color)",barBgColor:"var(--instrument-port-primary-color)"}}}return{dotColor:t?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)",barBgColor:t?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}}renderRot(){if(!this.rotType)return w;const{dotColor:e,barBgColor:t}=this.getRotColors();const i=this._rOff;if(this.rotType===sa.bar){const n=g1(this.rotStartAngle,this.rotEndAngle);const p=b1(this.rotPosition,i);const d=Number.isFinite(this.rotAtZeroDeadband)?this.rotAtZeroDeadband:Qa;if(n<Math.max(d,p)){return n2(t,this.rotStartAngle,this.rotPosition,i)}return c`
        ${l2({startAngle:this.rotStartAngle,endAngle:this.rotEndAngle,barColor:t,position:this.rotPosition,maskId:"rot-bar-mask",radiusOffset:i})}
        ${c`<g clip-path="url(#rot-bar-mask)">
            <g id="rot-spinner">
              ${s2(e,this.rotPosition,i)}
            </g>
          </g>`}
      `}const o=this.rotPriority??this.priority;const r=o===me.enhanced;let a=r?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";if(this.rotPortStarboard){if(this._rotationsPerMinute>0){a="var(--instrument-starboard-secondary-color)"}else if(this._rotationsPerMinute<0){a="var(--instrument-port-secondary-color)"}}return c`
      <g id="rot-spinner">
        ${a2(a,this.rotPosition,i)}
      </g>
    `}renderSetpoint(){if(this.angleSetpoint===void 0){return w}const e=Gd({state:this.state,priority:this.priority,atSetpoint:this.atAngleSetpoint,angleSetpoint:this.angleSetpoint,setpointAtZeroDeadband:this.angleSetpointAtZeroDeadband,newAngleSetpoint:this.newAngleSetpoint,touching:this.touching,setpointOverride:this.setpointOverride});const{visualState:t,colorMode:i,disabled:o,hasNewSetpoint:r}=e;const a=No(t);const n=f1+this._rOff+a-J2;const p=r?.75:1;const d=nr({visualState:t,colorMode:i,disabled:o,id:this._setpointId});const f=this.animateSetpoint;const g=this._departingNewAngleSetpoint!==void 0;const m=this.angleSetpoint+90;if(!this._setpointCssAngleInit){this._setpointCssAngle=m;this._setpointCssAngleInit=true}else{this._setpointCssAngle=Ud(this._setpointCssAngle,m)}const u=f?c`
        <g style="transform: rotate(${this._setpointCssAngle}deg) translateX(${-n}px) rotate(270deg); opacity: ${p}; transition: transform var(${io}, ${ko}) ease-out, opacity var(${io}, ${ko}) ease-out;">
          ${d}
        </g>
      `:c`
        <g transform="rotate(${this.angleSetpoint+90}) translate(${-n}, 0) rotate(270)" opacity="${p}">
          ${d}
        </g>
      `;if(r||g){const M=r;const C=M?this.newAngleSetpoint:this._departingNewAngleSetpoint;const A=M?1:0;const H=No(at.focus);const _=f1+this._rOff+H-J2;const S=nr({visualState:at.focus,colorMode:i,disabled:false,id:this._newSetpointId});if(f){const E=`var(${io}, ${ko})`;return c`
          ${u}
          <g style="transform: rotate(${C+90}deg) translateX(${-_}px) rotate(270deg); opacity: ${A}; transition: opacity ${E} ease-out;">
            ${S}
          </g>
        `}return c`
        ${u}
        <g transform="rotate(${C+90}) translate(${-_}, 0) rotate(270)" opacity="${A}">
          ${S}
        </g>
      `}return u}renderVesselImage(){if(this.vessels.length===0){return w}return this.vessels.map(e=>{let t;switch(e.size){case Dr.large:t=224;break;case Dr.medium:t=160;break;default:t=100}const i=t/160;return c`<g style="transform: ${e.transform} scale(${i}) translate(-80px, -80px) ">${ca[e.vesselImage]}</g>`})}renderStarboardPortIndicator(){if(!this.starboardPortIndicator){return w}return[la(0,180,"var(--instrument-starboard-secondary-color)","var(--instrument-starboard-secondary-color)"),la(180,360,"var(--instrument-port-secondary-color)","var(--instrument-port-secondary-color)")]}};pe.styles=Q(qd);ve([l({type:String})],pe.prototype,"state",2);ve([l({type:String})],pe.prototype,"priority",2);ve([l({type:String})],pe.prototype,"watchCircleType",2);ve([l({type:Boolean})],pe.prototype,"northArrow",2);ve([l({type:Boolean})],pe.prototype,"northArrowInside",2);ve([l({type:Number})],pe.prototype,"angleSetpoint",2);ve([l({type:Number})],pe.prototype,"newAngleSetpoint",2);ve([l({type:Boolean})],pe.prototype,"atAngleSetpoint",2);ve([l({type:Number})],pe.prototype,"angleSetpointAtZeroDeadband",2);ve([l({type:Boolean})],pe.prototype,"setpointOverride",2);ve([l({type:Boolean})],pe.prototype,"touching",2);ve([l({type:Boolean})],pe.prototype,"animateSetpoint",2);ve([Ve()],pe.prototype,"_departingNewAngleSetpoint",2);ve([l({type:Number})],pe.prototype,"padding",2);ve([l({type:Array,attribute:false})],pe.prototype,"areas",2);ve([l({type:Array,attribute:false})],pe.prototype,"barAreas",2);ve([l({type:Array,attribute:false})],pe.prototype,"needles",2);ve([l({type:Array,attribute:false})],pe.prototype,"tickmarks",2);ve([l({type:Boolean})],pe.prototype,"tickmarksInside",2);ve([l({type:String})],pe.prototype,"tickmarkStyle",2);ve([l({type:Array,attribute:false})],pe.prototype,"advices",2);ve([l({type:Boolean})],pe.prototype,"crosshairEnabled",2);ve([l({type:Boolean})],pe.prototype,"showLabels",2);ve([l({type:Array,attribute:false})],pe.prototype,"vessels",2);ve([l({type:Number})],pe.prototype,"wind",2);ve([l({type:Number})],pe.prototype,"windFromDirectionDeg",2);ve([l({type:Number})],pe.prototype,"windSymbolRadius",2);ve([l({type:String})],pe.prototype,"windColor",2);ve([l({type:Number})],pe.prototype,"current",2);ve([l({type:Number})],pe.prototype,"currentFromDirectionDeg",2);ve([l({type:Number})],pe.prototype,"currentSymbolRadius",2);ve([l({type:String})],pe.prototype,"currentColor",2);ve([l({type:Boolean})],pe.prototype,"starboardPortIndicator",2);ve([l({type:Number})],pe.prototype,"clipTop",2);ve([l({type:Number})],pe.prototype,"clipBottom",2);ve([l({type:Number})],pe.prototype,"scaleWindIcon",2);ve([l({type:Number})],pe.prototype,"rotation",2);ve([l({type:Boolean})],pe.prototype,"zoomToFitArc",2);ve([l({attribute:false})],pe.prototype,"arcFrame",2);ve([l({type:Number})],pe.prototype,"tickFadeAngle",2);ve([l({type:String})],pe.prototype,"rotType",2);ve([l({type:String})],pe.prototype,"rotPosition",2);ve([l({type:Number})],pe.prototype,"rotStartAngle",2);ve([l({type:Number})],pe.prototype,"rotEndAngle",2);ve([l({type:String})],pe.prototype,"rotPriority",2);ve([l({type:Boolean})],pe.prototype,"rotPortStarboard",2);ve([l({type:Number})],pe.prototype,"rotAtZeroDeadband",2);ve([l({type:Number})],pe.prototype,"rotationsPerMinute",1);pe=ve([x("obc-watch")],pe);var bl=(e=>{e["HDG"]="HDG";e["COG"]="COG";return e})(bl||{});function C1(e,t,i=me.regular,o=0){const r=i===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";if(e==="HDG"){return c`
      <g transform="rotate(${t}) translate(-256, ${-256-o})">

<path d="M254.654 100.32C255.219 99.1903 256.906 99.2277 257.396 100.433L272.312 137.092L272.388 137.301C273.067 139.455 270.647 141.314 268.676 140.13V140.129L256 132.582L243.323 140.129L243.324 140.13C241.289 141.352 238.777 139.332 239.688 137.092L254.604 100.433L254.654 100.32Z"
 fill=${r} stroke="var(--border-silhouette-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>
      </g>
    `}else if(e==="COG"){return c`
      <g transform="rotate(${t}) translate(-256, ${-256-o})">
<mask id="path-1-outside-1_133_32856" maskUnits="userSpaceOnUse" x="238" y="99" width="36" height="42" fill="black">
<rect fill="white" x="238" y="99" width="36" height="42"/>
<path fill-rule="evenodd" clip-rule="evenodd" vector-effect="non-scaling-stroke" d="M256 127.334L265.867 133.192L256 108.941L246.133 133.192L256 127.334ZM255.067 100.621C255.404 99.7929 256.596 99.7929 256.933 100.621L271.849 137.28C272.567 139.046 270.584 140.693 268.933 139.701L256 132L243.067 139.701C241.416 140.693 239.433 139.046 240.151 137.28L255.067 100.621Z"/>
</mask>
<path fill-rule="evenodd" clip-rule="evenodd" d="M256 127.334L265.867 133.192L256 108.941L246.133 133.192L256 127.334ZM255.067 100.621C255.404 99.7929 256.596 99.7929 256.933 100.621L271.849 137.28C272.567 139.046 270.584 140.693 268.933 139.701L256 132L243.067 139.701C241.416 140.693 239.433 139.046 240.151 137.28L255.067 100.621Z"
   fill=${r} />
<path d="M256 127.334L256.511 126.474L256 126.171L255.489 126.474L256 127.334ZM265.867 133.192L265.357 134.052L267.914 135.571L266.793 132.816L265.867 133.192ZM256 108.941L256.926 108.564L256 106.288L255.074 108.564L256 108.941ZM246.133 133.192L245.207 132.816L244.086 135.571L246.643 134.052L246.133 133.192ZM255.067 100.621L254.14 100.244L255.067 100.621ZM256.933 100.621L257.86 100.244L256.933 100.621ZM271.849 137.28L270.922 137.657L271.849 137.28ZM268.933 139.701L269.448 138.844L269.445 138.842L268.933 139.701ZM256 132L256.512 131.141L256 130.836L255.488 131.141L256 132ZM243.067 139.701L242.555 138.842L242.552 138.844L243.067 139.701ZM240.151 137.28L241.078 137.657L240.151 137.28ZM255.489 128.193L265.357 134.052L266.378 132.333L256.511 126.474L255.489 128.193ZM266.793 132.816L256.926 108.564L255.074 109.318L264.941 133.569L266.793 132.816ZM255.074 108.564L245.207 132.816L247.059 133.569L256.926 109.318L255.074 108.564ZM246.643 134.052L256.511 128.193L255.489 126.474L245.622 132.333L246.643 134.052ZM255.993 100.998C255.994 100.994 255.996 100.992 255.996 100.992C255.996 100.992 255.995 100.993 255.994 100.994C255.991 100.997 255.988 101 255.986 101.002C255.984 101.003 255.984 101.002 255.987 101.002C255.99 101.001 255.994 101 256 101C256.006 101 256.01 101.001 256.013 101.002C256.016 101.002 256.016 101.003 256.014 101.002C256.012 101 256.009 100.997 256.006 100.994C256.005 100.993 256.004 100.992 256.004 100.992C256.004 100.992 256.006 100.994 256.007 100.998L257.86 100.244C257.185 98.5852 254.815 98.5852 254.14 100.244L255.993 100.998ZM256.007 100.998L270.922 137.657L272.775 136.903L257.86 100.244L256.007 100.998ZM270.922 137.657C271.255 138.473 270.33 139.373 269.448 138.844L268.418 140.558C270.838 142.012 273.879 139.618 272.775 136.903L270.922 137.657ZM269.445 138.842L256.512 131.141L255.488 132.859L268.422 140.56L269.445 138.842ZM255.488 131.141L242.555 138.842L243.578 140.56L256.512 132.859L255.488 131.141ZM242.552 138.844C241.67 139.373 240.745 138.473 241.078 137.657L239.225 136.903C238.121 139.618 241.162 142.012 243.582 140.558L242.552 138.844ZM241.078 137.657L255.993 100.998L254.14 100.244L239.225 136.903L241.078 137.657Z" 
fill="var(--border-silhouette-color)" vector-effect="non-scaling-stroke" mask="url(#path-1-outside-1_133_32856)"/>

      </g>
    `}else{return[]}}var yl=class{constructor(t){this.atSetpoint=false;this.touching=false;this.autoAtSetpoint=true;this.setpointOverride=false;this.animateSetpoint=false;this.autoAtSetpointDeadband=t?.defaultDeadband??2;this.setpointAtZeroDeadband=t?.defaultZeroDeadband??.5;this._angularWraparound=t?.angularWraparound??false;this._onAnimationEnd=t?.onAnimationEnd}sync(t){const i=this.newSetpoint;if(t.setpoint!==void 0||"setpoint"in t)this.setpoint=t.setpoint;if(t.newSetpoint!==void 0||"newSetpoint"in t)this.newSetpoint=t.newSetpoint;if(t.atSetpoint!==void 0)this.atSetpoint=t.atSetpoint;if(t.touching!==void 0)this.touching=t.touching;if(t.autoAtSetpoint!==void 0)this.autoAtSetpoint=t.autoAtSetpoint;if(t.autoAtSetpointDeadband!==void 0)this.autoAtSetpointDeadband=t.autoAtSetpointDeadband;if(t.setpointAtZeroDeadband!==void 0)this.setpointAtZeroDeadband=t.setpointAtZeroDeadband;if(t.setpointOverride!==void 0)this.setpointOverride=t.setpointOverride;if(t.animateSetpoint!==void 0)this.animateSetpoint=t.animateSetpoint;if(i!==void 0&&this.newSetpoint===void 0&&this.animateSetpoint){this.departingNewSetpoint=i;clearTimeout(this._animationTimer);this._animationTimer=setTimeout(()=>{this.departingNewSetpoint=void 0;this._onAnimationEnd?.()},sl)}}dispose(){clearTimeout(this._animationTimer)}computeAtSetpoint(t){return aa({value:t,setpoint:this.setpoint,touching:this.touching,auto:this.autoAtSetpoint,deadband:this.autoAtSetpointDeadband,atSetpointManual:this.atSetpoint,angularWraparound:this._angularWraparound})}};var Nu=Object.defineProperty;var ju=Object.getOwnPropertyDescriptor;var Oe=(e,t,i,o)=>{var r=o>1?void 0:o?ju(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Nu(t,i,r);return r};var Ae=class extends k{constructor(){super(...arguments);this.heading=0;this.courseOverGround=0;this.headingSetpoint=null;this.atHeadingSetpoint=false;this.headingSetpointAtZeroDeadband=.5;this.headingSetpointOverride=false;this.autoAtHeadingSetpoint=true;this.autoAtHeadingSetpointDeadband=2;this.animateSetpoint=false;this.touching=false;this.headingAdvices=[];this.windSpeed=null;this.windFromDirection=null;this.currentSpeed=null;this.currentFromDirection=null;this.vesselImage=Er.genericTop;this.rotationsPerMinute=1;this.rotType=sa.dots;this.rotPosition=Ya.innerCircle;this.rotMaxValue=10;this.rotArcExtent=60;this.rotPortStarboard=false;this.rotAtZeroDeadband=Qa;this.direction="northUp";this.state=Le.active;this.priority=me.regular;this.priorityElements=["hdg"];this.showLabels=false;this.tickmarksInside=false;this._headingSp=new yl({angularWraparound:true,onAnimationEnd:()=>this.requestUpdate()});this._resizeController=new Lo(this,{})}willUpdate(e){super.willUpdate(e);this._headingSp.sync({setpoint:this.headingSetpoint??void 0,newSetpoint:this.newHeadingSetpoint,atSetpoint:this.atHeadingSetpoint,touching:this.touching,autoAtSetpoint:this.autoAtHeadingSetpoint,autoAtSetpointDeadband:this.autoAtHeadingSetpointDeadband,setpointAtZeroDeadband:this.headingSetpointAtZeroDeadband,setpointOverride:this.headingSetpointOverride,animateSetpoint:this.animateSetpoint})}disconnectedCallback(){super.disconnectedCallback();this._headingSp.dispose()}getPadding(){const e=Math.min(this.clientHeight,this.clientWidth);const t=512-e;const i=t/128;let o;if(t>0){o=i*48}else{o=i*6}return 72+o}get angleAdviceRaw(){return this.headingAdvices.map(({minAngle:e,maxAngle:t,hinted:i,type:o})=>{const r=this.heading>=e&&this.heading<=t?de.triggered:i?de.hinted:de.regular;return{minAngle:e,maxAngle:t,type:o,state:r}})}priorityFor(e){const t=Array.isArray(this.priorityElements)?this.priorityElements:[];return t.includes(e)?this.priority:me.regular}colorFor(e){return this.priorityFor(e)===me.enhanced?"var(--instrument-enhanced-secondary-color)":void 0}getRotation(){if(this.direction==="northUp"){return void 0}else if(this.direction==="headingUp"){return-this.heading}else if(this.direction==="courseUp"){return-this.courseOverGround}return void 0}render(){const e=[{angle:0,type:Te.main},{angle:90,type:Te.main},{angle:180,type:Te.main},{angle:270,type:Te.main}];const t=this.getPadding();const i=(176+t)*2;const o=`-${i/2} -${i/2} ${i} ${i}`;return h`
      <div class="container">
        <obc-watch
          .touching=${this.touching}
          .padding=${t}
          .advices=${this.angleAdviceRaw}
          .tickmarks=${e}
          .state=${this.state}
          .watchCircleType=${Lr.triple}
          .showLabels=${this.showLabels}
          .tickmarksInside=${this.tickmarksInside}
          .crosshairEnabled=${true}
          .northArrow=${true}
          .angleSetpoint=${this.headingSetpoint??void 0}
          .newAngleSetpoint=${this.newHeadingSetpoint}
          .atAngleSetpoint=${this._headingSp.computeAtSetpoint(this.heading)}
          .angleSetpointAtZeroDeadband=${this.headingSetpointAtZeroDeadband}
          .setpointOverride=${this.headingSetpointOverride}
          .priority=${this.priority}
          .animateSetpoint=${this.animateSetpoint}
          .vessels=${[{size:Dr.medium,vesselImage:this.vesselImage,transform:`rotate(${this.heading}deg)`}]}
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
          ${C1(bl.HDG,this.heading+(this.getRotation()??0),this.priorityFor("hdg"))}
          ${C1(bl.COG,this.courseOverGround+(this.getRotation()??0),this.priorityFor("cog"))}
        </svg>
      </div>
    `}};Ae.styles=L`
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
  `;Oe([l({type:Number})],Ae.prototype,"heading",2);Oe([l({type:Number})],Ae.prototype,"courseOverGround",2);Oe([l({type:Number})],Ae.prototype,"headingSetpoint",2);Oe([l({type:Number})],Ae.prototype,"newHeadingSetpoint",2);Oe([l({type:Boolean})],Ae.prototype,"atHeadingSetpoint",2);Oe([l({type:Number})],Ae.prototype,"headingSetpointAtZeroDeadband",2);Oe([l({type:Boolean})],Ae.prototype,"headingSetpointOverride",2);Oe([l({type:Boolean,attribute:false})],Ae.prototype,"autoAtHeadingSetpoint",2);Oe([l({type:Number})],Ae.prototype,"autoAtHeadingSetpointDeadband",2);Oe([l({type:Boolean})],Ae.prototype,"animateSetpoint",2);Oe([l({type:Boolean})],Ae.prototype,"touching",2);Oe([l({type:Array,attribute:false})],Ae.prototype,"headingAdvices",2);Oe([l({type:Number})],Ae.prototype,"windSpeed",2);Oe([l({type:Number})],Ae.prototype,"windFromDirection",2);Oe([l({type:Number})],Ae.prototype,"currentSpeed",2);Oe([l({type:Number})],Ae.prototype,"currentFromDirection",2);Oe([l({type:String})],Ae.prototype,"vesselImage",2);Oe([l({type:Number})],Ae.prototype,"rotationsPerMinute",2);Oe([l({type:String})],Ae.prototype,"rotType",2);Oe([l({type:String})],Ae.prototype,"rotPosition",2);Oe([l({type:Number})],Ae.prototype,"rotMaxValue",2);Oe([l({type:Number})],Ae.prototype,"rotArcExtent",2);Oe([l({type:Boolean})],Ae.prototype,"rotPortStarboard",2);Oe([l({type:Number})],Ae.prototype,"rotAtZeroDeadband",2);Oe([l({type:String})],Ae.prototype,"direction",2);Oe([l({type:String})],Ae.prototype,"state",2);Oe([l({type:String})],Ae.prototype,"priority",2);Oe([l({type:Array,attribute:false})],Ae.prototype,"priorityElements",2);Oe([l({type:Boolean})],Ae.prototype,"showLabels",2);Oe([l({type:Boolean})],Ae.prototype,"tickmarksInside",2);Ae=Oe([x("obc-compass")],Ae);function k1({height:e,minValue:t,maxValue:i,min:o,max:r,fill:a,stroke:n,x1:p}){const d=8;const f=4;const g=p+d+f;const m=d/2;const u=xr(o,t,i,e)-2*m;const M=xr(r,t,i,e)+2*m;const C=`M ${p+f} ${u} 
                    A ${m} ${m} 0 0 0 ${g} ${u}
                    V ${M}
                    A ${m} ${m} 0 0 0 ${p+f} ${M}
                    Z`;return c`<path d=${C} fill=${a} stroke=${n} stroke-width="1" vector-effect="non-scaling-stroke" />`}function wl({height:e,scaleWidth:t,minValue:i,maxValue:o,value:r,style:a,x1:n}){if(r>=o||r<=i){return null}const p=bi(a);const d=xr(r,i,o,e);return c`<line x1=${n-2} x2=${n+t} y1=${d}  y2=${d} stroke=${p} stroke-width="1" vector-effect="non-scaling-stroke"/>`}function rp(e,t,i,o,r,a){const n=o/2-r;const p=-o/2;const d=o/2-r;const f=[];if(a.min>t){const g=xr(a.min,t,i,e);f.push(c`<line x1=${p} x2=${d} y1=${g} y2=${g} 
                    stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke" 
                    stroke-dasharray="4 4"/>`)}if(a.max<i){const g=xr(a.max,t,i,e);f.push(c`<line x1=${p} x2=${d} y1=${g} y2=${g} 
                    stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke" 
                    stroke-dasharray="4 4"/>`)}if(a.type===dt.caution){let g;let m="var(--instrument-frame-primary-color)";if(a.state===de.hinted){g="var(--instrument-frame-tertiary-color)"}else if(a.state===de.regular){g="var(--instrument-tick-mark-tertiary-color)"}else{g="var(--on-caution-active-color)";m="var(--alert-caution-color)"}const u=[];const M=50;for(let H=-16*8;H<16*14;H+=16){u.push(c`<g transform="translate(0 ${-H}) ">
            <path d="M 50 0 L 0 ${M}" stroke=${g} stroke-width="6"/>
            </g>
            `)}const C=`adviceMask-${a.min}-${a.max}`;let A=He.regular;if(a.state===de.regular){A=He.regular}else if(a.state===de.triggered){A=He.enhanced}return c`
            <mask id=${C}>
                ${k1({height:e,minValue:t,maxValue:i,min:a.min,max:a.max,fill:"white",stroke:"black",x1:n})}
            </mask>
            <g mask="url(#${C})">
                ${m?c`<rect x="-256" y="-512" width="512" height="1024" fill="${m}"/>`:w}
                ${u}
            </g>
            ${k1({height:e,minValue:t,maxValue:i,min:a.min,max:a.max,fill:"none",stroke:g,x1:n})}
            ${wl({height:e,scaleWidth:r,minValue:t,maxValue:i,value:a.min,style:A,x1:n})}
            ${wl({height:e,scaleWidth:r,minValue:t,maxValue:i,value:a.max,style:A,x1:n})}
            ${f}
        `}else{let g;let m;let u;if(a.state===de.hinted){g="var(--instrument-frame-tertiary-color)";u="var(--instrument-frame-primary-color)";m=He.regular}else if(a.state===de.regular){g="var(--instrument-regular-secondary-color)";u="var(--instrument-frame-primary-color)";m=He.regular}else{g="var(--instrument-enhanced-secondary-color)";u=g;m=He.regular}return c`
            ${k1({height:e,minValue:t,maxValue:i,min:a.min,max:a.max,fill:u,stroke:g,x1:n})}
            ${wl({height:e,scaleWidth:r,minValue:t,maxValue:i,value:a.min,style:m,x1:n})}
            ${wl({height:e,scaleWidth:r,minValue:t,maxValue:i,value:a.max,style:m,x1:n})}
            ${f}
        `}}function ip({height:e,width:t,scaleWidth:i,minValue:o,maxValue:r},a,n,p,d,f,g){const m=8;const u=`M -${t/2} 0  V -${e/2-8}  a 8 8 0 0 1 8 -8 h ${t-m*2} a 8 8 0 0 1 8 8 V ${e/2-m} a 8 8 0 0 1 -8 8 h -${t-2*m} a 8 8 0 0 1 -8 -8 Z`;const M=c`
      <path d=${u} 
       fill=${p.container}
       />
  `;const C=t-i-m;let A=c`
      <path d="M -${t/2} 0  V -${e/2-m}  a 8 8 0 0 1 8 -8 h ${C} V ${e/2} h -${C} a 8 8 0 0 1 -8 -8 Z" 
       stroke="var(--instrument-frame-secondary-color)"
       fill="var(--instrument-frame-secondary-color)"
       vector-effect="non-scaling-stroke"
       />
  `;const H=c`
      <path d=${u} 
      stroke="var(--instrument-frame-tertiary-color)" 
      fill="none" 
      vector-effect="non-scaling-stroke"/>
  `;if(d.off){A=w}const{boxFill:_,boxStroke:S,barFill:E,barStroke:D}=Fu(d.priority===me.enhanced);const K=[];const I="boxMask";const Y=d.hideContainer?w:c`
  <defs>
  <mask id=${I}>
  <path d=${u} fill="white" stroke="white" vector-effect="non-scaling-stroke"/>
  </defs>`;const R=d.hideContainer?void 0:`url(#${I})`;const B=[];if(f.mainTickmarks){for(const P of f.mainTickmarks){if(P<o||P>r)continue;const be=xr(P,o,r,e);K.push(c`<line x1=${-t/2} x2=${t/2} y1=${be} y2=${be} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`);B.push(P)}}const F=t/2-i+4;if(f.primaryTickmarkInterval!==void 0&&f.primaryTickmarkInterval>0&&Number.isFinite(f.primaryTickmarkInterval)){const{svgs:P,values:be}=op({height:e,interval:f.primaryTickmarkInterval,minValue:o,maxValue:r,tickmarksX:F,tickmarksWidth:t/2-F,skipValues:B});K.push(...P);B.push(...be)}if(f.secondaryTickmarkInterval!==void 0&&f.secondaryTickmarkInterval>0&&Number.isFinite(f.secondaryTickmarkInterval)){const{svgs:P,values:be}=op({height:e,interval:f.secondaryTickmarkInterval,minValue:o,maxValue:r,tickmarksX:F,tickmarksWidth:8,skipValues:B});K.push(...P);B.push(...be)}const z=-t/2;const ee=t-i;const T=a.map(P=>{const be=xr(P.min,o,r,e);const he=xr(P.max,o,r,e);const se=Math.min(be,he);const ke=Math.abs(he-be);return c`<rect width=${ee} height=${ke} x=${z} y=${se} fill=${P.fill??_} stroke=${P.fill??S} vector-effect="non-scaling-stroke"/>`});const Z=g.map(P=>rp(e,o,r,t,i,P));const q=n?c`
<rect x=${z} y=${xr(n.value,o,r,e)-4} width=${ee} height="8" rx="4" fill=${E} stroke=${D} vector-effect="non-scaling-stroke"/>
`:w;const j=[Y,H,c`<g mask=${R}>${K}${T} </g>`,Z,q];if(!d.hideContainer){j.splice(0,0,[M,A])}return j}function xr(e,t,i,o){const r=i-t;return(-e+t)*o/r+o/2}function op({height:e,interval:t,tickmarksX:i,tickmarksWidth:o,minValue:r,maxValue:a,skipValues:n}){const p=[];const d=[];for(let f=0;f<a;f+=t){if(n.includes(f)){continue}const g=xr(f,r,a,e);d.push(f);p.push(c`<line x1=${i} x2=${i+o} y1=${g} y2=${g} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`)}for(let f=-t;f>r;f-=t){if(n.includes(f)){continue}const g=xr(f,r,a,e);d.push(f);p.push(c`<line x1=${i} x2=${i+o} y1=${g} y2=${g} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`)}return{svgs:p,values:d}}function Fu(e){if(e){return{boxFill:"var(--instrument-enhanced-tertiary-color)",boxStroke:"var(--instrument-enhanced-tertiary-color)",barFill:"var(--instrument-enhanced-secondary-color)",barStroke:"var(--instrument-enhanced-tertiary-color)"}}else{return{boxFill:"var(--instrument-regular-tertiary-color)",boxStroke:"var(--instrument-regular-tertiary-color)",barFill:"var(--instrument-regular-secondary-color)",barStroke:"var(--instrument-regular-tertiary-color)"}}}var Uu=Object.defineProperty;var Wu=Object.getOwnPropertyDescriptor;var ao=(e,t,i,o)=>{var r=o>1?void 0:o?Wu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Uu(t,i,r);return r};var $r=class extends k{constructor(){super(...arguments);this.depth=0;this.draft=0;this.advice=[];this.vesselScale=1;this.instrumentRange=10;this.primaryTickmarkInterval=50;this.secondaryTickmarkInterval=10;this.vesselImage=Er.psvFore;this.priority=me.regular;this._boxWidth=336;this._gaugeWidth=72;this._scaleWidth=24}_toValue(e){return-e}_toTranslatedValue(e){return e*(this._boxWidth/2)/this.instrumentRange}_getAdvice(){return this.advice.map(e=>{const t=this.depth>=e.min&&this.depth<=e.max;const i=t?de.triggered:e.hinted?de.hinted:de.regular;return{...e,min:this._toValue(e.max),max:this._toValue(e.min),state:i}})}render(){const e=this._boxWidth/2-this._gaugeWidth/2;const t=8;const i=c`
    <rect fill="url(#seabedPattern)" y=${this._toTranslatedValue(this.depth)} x=${-this._boxWidth/2} width=${this._boxWidth-this._gaugeWidth} height=${this._toTranslatedValue(this.instrumentRange-this.depth)} fill="red" />
    `;const o=this.priority===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";const r=this.vesselScale*50/this.instrumentRange;return h`
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

          <g transform="translate(${e}, ${this._boxWidth/4})">
            ${ip({height:this._boxWidth/2,minValue:this._toValue(this.instrumentRange),maxValue:this._toValue(0),width:this._gaugeWidth,scaleWidth:this._scaleWidth},[{min:this._toValue(this.depth),max:this._toValue(0)},{min:this._toValue(this.draft),max:this._toValue(0),fill:o}],{value:this._toValue(this.depth)},{container:"var(--instrument-frame-primary-color)"},{hideContainer:false,off:false,priority:this.priority},{primaryTickmarkInterval:this.primaryTickmarkInterval,secondaryTickmarkInterval:this.secondaryTickmarkInterval},this._getAdvice())}
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
                rx=${t}
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
              ${this.vesselImage?ca[this.vesselImage]:w}
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
            V -${this._boxWidth/2-t}
             a ${t} ${t} 0 0 0 ${-t} ${-t}
             H ${-this._boxWidth/2+t} 
             a ${t} ${t} 0 0 0 ${-t} ${t}
             V ${this._boxWidth/2-t}
             a ${t} ${t} 0 0 0 ${t} ${t}
             H ${this._boxWidth/2-this._gaugeWidth}"
            stroke="var(--instrument-frame-tertiary-color)"
            fill="none"
            vector-effect="non-scaling-stroke"
          />
        </svg>
      </div>
    `}};$r.styles=L`
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
  `;ao([l({type:Number})],$r.prototype,"depth",2);ao([l({type:Number})],$r.prototype,"draft",2);ao([l({type:Array})],$r.prototype,"advice",2);ao([l({type:Number})],$r.prototype,"vesselScale",2);ao([l({type:Number})],$r.prototype,"instrumentRange",2);ao([l({type:Number})],$r.prototype,"primaryTickmarkInterval",2);ao([l({type:Number})],$r.prototype,"secondaryTickmarkInterval",2);ao([l({type:String})],$r.prototype,"vesselImage",2);ao([l({type:String})],$r.prototype,"priority",2);$r=ao([x("obc-depth-actual")],$r);var Gu=Object.defineProperty;var qu=Object.getOwnPropertyDescriptor;var Nt=(e,t,i,o)=>{var r=o>1?void 0:o?qu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Gu(t,i,r);return r};var _t=class extends k{constructor(){super(...arguments);this.pitch=0;this.roll=0;this.minAvgPitch=0;this.maxAvgPitch=0;this.minAvgRoll=0;this.maxAvgRoll=0;this.vesselImageFore=Er.psvFore;this.vesselImageSide=Er.psvSide;this.maxPitchAdvice=void 0;this.maxRollAdvice=void 0;this.triggerPitchAdvice=false;this.triggerRollAdvice=false;this.priority=me.regular;this.priorityElements=["pitch","roll"]}priorityFor(e){const t=Array.isArray(this.priorityElements)?this.priorityElements:[];return t.includes(e)?this.priority:me.regular}needleColor(e){return this.priorityFor(e)===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}barColor(e){return this.priorityFor(e)===me.enhanced?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)"}render(){return h`
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
          .watchCircleType=${Lr.double}
          .areas=${[{startAngle:60,endAngle:120,roundOutsideCut:true,roundInsideCut:true},{startAngle:240,endAngle:300,roundOutsideCut:true,roundInsideCut:true},{startAngle:315,endAngle:45,roundOutsideCut:true,roundInsideCut:true},{startAngle:135,endAngle:225,roundOutsideCut:true,roundInsideCut:true}]}
          .barAreas=${[{startAngle:this.minAvgRoll,endAngle:this.maxAvgRoll,fillColor:this.barColor("roll")},{startAngle:180+this.minAvgRoll,endAngle:180+this.maxAvgRoll,fillColor:this.barColor("roll")},{startAngle:90+this.minAvgPitch,endAngle:90+this.maxAvgPitch,fillColor:this.barColor("pitch")},{startAngle:270+this.minAvgPitch,endAngle:270+this.maxAvgPitch,fillColor:this.barColor("pitch")}]}
          .needles=${[{angle:this.roll,fillColor:this.needleColor("roll"),strokeColor:"var(--border-silhouette-color)"},{angle:180+this.roll,fillColor:this.needleColor("roll"),strokeColor:"var(--border-silhouette-color)"},{angle:90+this.pitch,fillColor:this.needleColor("pitch"),strokeColor:"var(--border-silhouette-color)"},{angle:270+this.pitch,fillColor:this.needleColor("pitch"),strokeColor:"var(--border-silhouette-color)"}]}
          .vessels=${[{size:Dr.large,vesselImage:this.vesselImageSide,transform:`rotate(${this.pitch}deg)`},{size:Dr.large,vesselImage:this.vesselImageFore,transform:`rotate(${this.roll}deg)`}]}
          .tickmarks=${[{angle:0,type:Te.main},{angle:90,type:Te.main},{angle:180,type:Te.main},{angle:270,type:Te.main}]}
          .advices=${this.advices}
        ></obc-watch>
      </div>
    `}get advices(){const e=[];if(this.maxPitchAdvice!==void 0){const t=this.triggerPitchAdvice?de.triggered:de.regular;e.push({minAngle:60,maxAngle:90-this.maxPitchAdvice,type:dt.caution,state:t,hideMinTickmark:true});e.push({minAngle:90+this.maxPitchAdvice,maxAngle:120,type:dt.caution,state:t,hideMaxTickmark:true});e.push({minAngle:240,maxAngle:270-this.maxPitchAdvice,type:dt.caution,state:t,hideMinTickmark:true});e.push({minAngle:270+this.maxPitchAdvice,maxAngle:300,type:dt.caution,state:t,hideMaxTickmark:true})}if(this.maxRollAdvice!==void 0){const t=this.triggerRollAdvice?de.triggered:de.regular;e.push({minAngle:-45,maxAngle:-this.maxRollAdvice,type:dt.caution,state:t,hideMinTickmark:true});e.push({minAngle:this.maxRollAdvice,maxAngle:45,type:dt.caution,state:t,hideMaxTickmark:true});e.push({minAngle:135,maxAngle:180-this.maxRollAdvice,type:dt.caution,state:t,hideMinTickmark:true});e.push({minAngle:180+this.maxRollAdvice,maxAngle:225,type:dt.caution,state:t,hideMaxTickmark:true})}return e}};_t.styles=L`
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
  `;Nt([l({type:Number})],_t.prototype,"pitch",2);Nt([l({type:Number})],_t.prototype,"roll",2);Nt([l({type:Number})],_t.prototype,"minAvgPitch",2);Nt([l({type:Number})],_t.prototype,"maxAvgPitch",2);Nt([l({type:Number})],_t.prototype,"minAvgRoll",2);Nt([l({type:Number})],_t.prototype,"maxAvgRoll",2);Nt([l({type:String})],_t.prototype,"vesselImageFore",2);Nt([l({type:String})],_t.prototype,"vesselImageSide",2);Nt([l({type:Number})],_t.prototype,"maxPitchAdvice",2);Nt([l({type:Number})],_t.prototype,"maxRollAdvice",2);Nt([l({type:Boolean})],_t.prototype,"triggerPitchAdvice",2);Nt([l({type:Boolean})],_t.prototype,"triggerRollAdvice",2);Nt([l({type:String})],_t.prototype,"priority",2);Nt([l({type:Array,attribute:false})],_t.prototype,"priorityElements",2);_t=Nt([x("obc-pitch-roll")],_t);var ap=L`
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
`;var Yu=Object.defineProperty;var Qu=Object.getOwnPropertyDescriptor;var no=(e,t,i,o)=>{var r=o>1?void 0:o?Qu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Yu(t,i,r);return r};var pa=(e=>{e["icon"]="icon";e["text"]="text";e["iconTextUnder"]="icon-text-under";e["iconText"]="text-icon";return e})(pa||{});var wi=(e=>{e["flat"]="flat";e["regular"]="regular";e["normal"]="normal";return e})(wi||{});var Mr=class extends k{constructor(){super(...arguments);this.value="value";this.selected=false;this.activated=false;this.type="text";this.variant="regular";this.hugText=false;this.showDivider=true;this.disabled=false;this.large=false}onClick(e){if(this.disabled){e.preventDefault();return}if(!this.selected){this.dispatchEvent(new CustomEvent("selected",{detail:{value:this.value}}))}}render(){const e=this.type==="text"||this.type==="text-icon";const t=this.type!=="text";const i=this.type!=="icon";const o=this.type==="icon-text-under";return h`
      <button
        class=${J({wrapper:true,selected:this.selected,"inline-label":e,"type-flat":this.variant==="flat","type-regular":this.variant==="regular","type-normal":this.variant==="normal","icon-text-under":o,"hug-text":this.hugText,disabled:this.disabled,activated:this.activated,large:this.large})}
        ?disabled=${this.disabled}
        @click=${this.onClick}
      >
        <div class="visible-wrapper" part="visible-wrapper">
          ${t?h`<div class="icon" part="icon">
                <slot name="icon"></slot>
              </div>`:""}
          ${i&&!o?h`<div class="label"><slot></slot></div>`:""}
        </div>
        ${i&&o?h`<div class="label-container">
              <div class="label"><slot></slot></div>
            </div>`:""}
      </button>
    `}};Mr.styles=Q(ap);no([l({type:String})],Mr.prototype,"value",2);no([l({type:Boolean,reflect:true})],Mr.prototype,"selected",2);no([l({type:Boolean,reflect:true})],Mr.prototype,"activated",2);no([l({type:String})],Mr.prototype,"type",2);no([l({type:String})],Mr.prototype,"variant",2);no([l({type:Boolean})],Mr.prototype,"hugText",2);no([l({type:Boolean,reflect:true})],Mr.prototype,"showDivider",2);no([l({type:Boolean,reflect:true})],Mr.prototype,"disabled",2);no([l({type:Boolean,reflect:true})],Mr.prototype,"large",2);Mr=no([x("obc-toggle-button-option")],Mr);var np=L`
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
`;var Ku=Object.defineProperty;var Xu=Object.getOwnPropertyDescriptor;var lo=(e,t,i,o)=>{var r=o>1?void 0:o?Xu(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Ku(t,i,r);return r};var Hr=class extends k{constructor(){super(...arguments);this.value="";this.type=pa.text;this.variant=wi.regular;this.hugText=false;this.externalControl=false;this.disabled=false;this.large=false;this._originalDisabledStates=new Map}hasAnyEnabledOption(){if(this.disabled)return false;return Array.from(this.options).some(e=>!e.disabled)}canSelectOption(e){if(this.disabled)return false;const t=this.getOptionByValue(e);return t!==null&&!t.disabled}getOptionByValue(e){return Array.from(this.options).find(t=>t.value===e)||null}getFirstSelectableOption(){if(this.disabled)return null;return Array.from(this.options).find(e=>!e.disabled)||null}updateSelection(e,t=true){const i=this.value;if(!this.hasAnyEnabledOption()){this.options.forEach(o=>{o.selected=o.value===this.value});this.setNoDivider();return}if(!this.canSelectOption(e)){if(this.value&&this.getOptionByValue(this.value)){this.options.forEach(r=>{r.selected=r.value===this.value});this.setNoDivider();return}const o=this.getFirstSelectableOption();e=o?.value||""}this.value=e;this.options.forEach(o=>{o.selected=o.value===e});this.setNoDivider();if(t&&i!==e){this.dispatchEvent(new CustomEvent("value",{detail:{value:e,previousValue:i}}))}}updateActivated(e){if(e){this.options.forEach(t=>{t.activated=t.value===e})}else{this.options.forEach(t=>{t.activated=false})}}setNoDivider(){const e=Array.from(this.options).findIndex(i=>i.selected);this.options.forEach(i=>{i.showDivider=true});if(e===-1){return}const t=this.options[e+1];if(t){t.showDivider=false}}firstUpdated(e){super.firstUpdated(e);const t=Array.from(this.options).map(o=>o.value);const i=new Set(t);if(t.length!==i.size){console.warn("Toggle button group has duplicate values. This may cause unexpected behavior.")}this.options.forEach(o=>{this._originalDisabledStates.set(o,o.hasAttribute("disabled"));o.addEventListener("selected",a=>this.handleOptionClick(a));const r=new MutationObserver(a=>{a.forEach(n=>{if(n.attributeName==="disabled"&&!o.hasAttribute("data-group-disabled")){this._originalDisabledStates.set(o,o.hasAttribute("disabled"));this.handleOptionDisabledChange()}})});r.observe(o,{attributes:true,attributeFilter:["disabled"]});o.type=this.type;o.variant=this.variant;o.hugText=this.hugText;o.large=this.large;if(this.disabled){o.setAttribute("data-group-disabled","true");o.disabled=true}});if(!this.value||!this.getOptionByValue(this.value)){const o=this.getFirstSelectableOption();if(o){this.updateSelection(o.value,false)}}else{this.updateSelection(this.value,false)}if(this.activated){this.updateActivated(this.activated)}}handleOptionDisabledChange(){const e=this.getOptionByValue(this.value);if(e?.disabled&&this.hasAnyEnabledOption()){const t=this.getFirstSelectableOption();if(t){this.updateSelection(t.value)}}}handleOptionClick(e){const{value:t}=e.detail;if(this.externalControl){this.dispatchEvent(new CustomEvent("value",{detail:{value:t,previousValue:this.value}}))}else{this.updateSelection(t)}}willUpdate(e){if(e.has("value")){this.updateSelection(this.value)}if(e.has("activated")){this.updateActivated(this.activated)}if(e.has("type")||e.has("variant")||e.has("hugText")||e.has("large")){this.options.forEach(t=>{t.type=this.type;t.variant=this.variant;t.hugText=this.hugText;t.large=this.large})}if(e.has("disabled")){this.options.forEach(t=>{if(this.disabled){t.setAttribute("data-group-disabled","true");t.disabled=true}else{t.removeAttribute("data-group-disabled");const i=this._originalDisabledStates.get(t)||false;t.disabled=i}})}}updated(e){super.updated(e);const t=this.getOptionByValue(this.value);if(t?.disabled&&this.hasAnyEnabledOption()){const i=this.getFirstSelectableOption();if(i){this.updateSelection(i.value)}}}render(){const e={"outer-wrapper":true,flat:this.variant===wi.flat,regular:this.variant===wi.regular,"hug-text":this.hugText,"icon-text-under":this.type===pa.iconTextUnder,disabled:this.disabled,large:this.large};return h`
      <div class=${J(e)}>
        <div class="wrapper">
          <slot></slot>
        </div>
      </div>
    `}};Hr.styles=Q(np);lo([l({type:String})],Hr.prototype,"value",2);lo([l({type:String})],Hr.prototype,"activated",2);lo([l({type:String})],Hr.prototype,"type",2);lo([l({type:String})],Hr.prototype,"variant",2);lo([l({type:Boolean})],Hr.prototype,"hugText",2);lo([l({type:Boolean})],Hr.prototype,"externalControl",2);lo([l({type:Boolean,reflect:true})],Hr.prototype,"disabled",2);lo([l({type:Boolean,reflect:true})],Hr.prototype,"large",2);lo([hd({selector:"obc-toggle-button-option"})],Hr.prototype,"options",2);Hr=lo([x("obc-toggle-button-group")],Hr);var lp=L`
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
`;var sp=L`
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
`;var Ju=Object.defineProperty;var e9=Object.getOwnPropertyDescriptor;var Sr=(e,t,i,o)=>{var r=o>1?void 0:o?e9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Ju(t,i,r);return r};var Ja=(e=>{e["Normal"]="normal";e["Enhanced"]="enhanced";e["NoInput"]="no-input";return e})(Ja||{});var Yt=class extends k{constructor(){super(...arguments);this.value=50;this.min=0;this.max=100;this.stepClick=10;this.variant="normal";this.hasLeftIcon=false;this.hasRightIcon=false;this.allowSeeking=false;this.seekingSpeed=1/3;this.disabled=false;this.animationFrame=null;this.isMouseDown=false;this.isTouchActive=false;this.targetValue=0;this.isDragging=false;this.animationStartTime=null;this.animationStartValue=0;this.onWindowMouseMove=e=>{this.onMouseMove(e)};this.onWindowMouseUp=()=>{this.onMouseUp()};this.onWindowTouchMove=e=>{this.onTouchMove(e)};this.onWindowTouchEnd=()=>{this.onTouchEnd()}}get ratio(){const e=this.max-this.min;if(!Number.isFinite(e)||e<=0)return 0;const t=(this.value-this.min)/e;if(!Number.isFinite(t))return 0;return Math.max(0,Math.min(1,t))}onInput(e){this.value=e;this.dispatchEvent(new CustomEvent("value",{detail:this.value}))}onReduceClick(){if(this.disabled)return;this.onInput(Math.max(this.value-this.stepClick,this.min))}onIncreaseClick(){if(this.disabled)return;this.onInput(Math.min(this.value+this.stepClick,this.max))}get slider(){return this.renderRoot.querySelector('input[type="range"]')}isClickingThumb(e){const t=this.slider.getBoundingClientRect();const i=t.left+24;const o=t.width-48;const r=48;const a=this.ratio;const n=i+o*a;let p;if("touches"in e){p=e.touches[0].clientX}else{p=e.clientX}const d=Math.abs(p-n)<=r/2;return d}onMouseDown(e){if(this.variant==="no-input"||this.disabled)return;if(this.isClickingThumb(e))return;this.isMouseDown=true;this.updateTargetValue(e);e.preventDefault();window.addEventListener("mousemove",this.onWindowMouseMove);window.addEventListener("mouseup",this.onWindowMouseUp);this.startAnimation()}onTouchStart(e){if(this.variant==="no-input"||this.disabled)return;if(this.isClickingThumb(e))return;this.isTouchActive=true;this.updateTargetValue(e);e.preventDefault();window.addEventListener("touchmove",this.onWindowTouchMove,{passive:false});window.addEventListener("touchend",this.onWindowTouchEnd);this.startAnimation()}onMouseMove(e){if(this.isMouseDown){this.updateTargetValue(e)}}onTouchMove(e){if(this.isTouchActive){this.updateTargetValue(e)}}onMouseUp(){this.isMouseDown=false;window.removeEventListener("mousemove",this.onWindowMouseMove);window.removeEventListener("mouseup",this.onWindowMouseUp);this.stopAnimation()}onTouchEnd(){this.isTouchActive=false;window.removeEventListener("touchmove",this.onWindowTouchMove);window.removeEventListener("touchend",this.onWindowTouchEnd);this.stopAnimation()}updateTargetValue(e){const t=this.slider.getBoundingClientRect();const i=t.left+24;const o=t.width-48;const r=e instanceof MouseEvent?e.clientX:e.touches[0].clientX;const a=(r-i)/o;const n=parseFloat(this.slider.min);const p=parseFloat(this.slider.max);const d=n+(p-n)*a;if(this.step){this.targetValue=Math.round(d/this.step)*this.step}else{this.targetValue=d}}startAnimation(){this.isDragging=this.allowSeeking;this.animationStartTime=performance.now();this.animationStartValue=parseFloat(this.slider.value);const e=parseFloat(this.slider.min);const t=parseFloat(this.slider.max);const i=this.step;const o=1/this.seekingSpeed*1e3;const r=this.targetValue>this.animationStartValue?1:-1;const a=()=>{let n=this.targetValue;if(!this.isDragging){const p=performance.now();const d=p-(this.animationStartTime??p);const f=Math.abs(t-e);const g=Math.min(d/o,1);const m=this.animationStartValue+r*f*g;if(r>0){n=i===void 0?m:Math.ceil((m-e)/i)*i+e;n=Math.min(this.targetValue,n)}else{n=i===void 0?m:Math.floor((m-e)/i)*i+e;n=Math.max(this.targetValue,n)}}if(parseFloat(this.slider.value)!==n){this.slider.value=String(n);this.slider.dispatchEvent(new Event("input"))}if(r>0&&n<this.targetValue||r<0&&n>this.targetValue){this.animationFrame=requestAnimationFrame(a)}else if(this.isMouseDown||this.isTouchActive){this.animationStartTime=performance.now();this.animationStartValue=parseFloat(this.slider.value);this.animationFrame=requestAnimationFrame(a);this.isDragging=true}};this.animationFrame=requestAnimationFrame(a)}stopAnimation(){if(this.animationFrame!==null){cancelAnimationFrame(this.animationFrame);this.animationFrame=null}}render(){return h`
      ${this.hasLeftIcon?h` <obc-icon-button
            ?disabled=${this.disabled}
            @click=${this.onReduceClick}
            variant="normal"
          >
            <slot name="icon-left"></slot>
          </obc-icon-button>`:null}
      <div
        class=${J({wrapper:true,[this.variant]:true,disabled:this.disabled})}
        style=${da({"--_ratio":String(this.ratio)})}
      >
        <div class="track"></div>
        <input
          type="range"
          min=${this.min}
          max=${this.max}
          step=${$e(this.step)}
          .value=${this.value.toString()}
          ?disabled=${this.variant==="no-input"||this.disabled}
          class="slider"
          @input=${e=>{this.value=Number(e.target.value);this.dispatchEvent(new CustomEvent("value",{detail:this.value}))}}
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
      ${this.hasRightIcon?h`<obc-icon-button
            ?disabled=${this.disabled}
            @click=${this.onIncreaseClick}
            variant="normal"
          >
            <slot name="icon-right"></slot>
          </obc-icon-button>`:null}
    `}};Yt.styles=Q(sp);Sr([l({type:Number})],Yt.prototype,"value",2);Sr([l({type:Number})],Yt.prototype,"min",2);Sr([l({type:Number})],Yt.prototype,"max",2);Sr([l({type:Number})],Yt.prototype,"step",2);Sr([l({type:Number})],Yt.prototype,"stepClick",2);Sr([l({type:String})],Yt.prototype,"variant",2);Sr([l({type:Boolean})],Yt.prototype,"hasLeftIcon",2);Sr([l({type:Boolean})],Yt.prototype,"hasRightIcon",2);Sr([l({type:Boolean})],Yt.prototype,"allowSeeking",2);Sr([l({type:Number})],Yt.prototype,"seekingSpeed",2);Sr([l({type:Boolean})],Yt.prototype,"disabled",2);Yt=Sr([x("obc-slider")],Yt);var cp=L`
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
`;var t9=Object.defineProperty;var r9=Object.getOwnPropertyDescriptor;var xo=(e,t,i,o)=>{var r=o>1?void 0:o?r9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)t9(t,i,r);return r};var Rr=class extends k{constructor(){super(...arguments);this.label="Label";this.checked=false;this.disabled=false;this.hasDescription=false;this.description="";this.hasBottomDivider=false;this.hasIcon=false;this.externalControl=false}_tryChange(e){if(this.disabled){e.preventDefault();return}const t=!this.checked;if(!this.externalControl){this.checked=t}e.stopPropagation();this.dispatchEvent(new CustomEvent("input",{detail:{checked:t}}));if(this.externalControl){e.target.checked=this.checked}}render(){return h`
      <label
        class=${J({checked:this.checked,disabled:this.disabled,"has-description":this.hasDescription})}
      >
        <div class="icon-label-container">
          ${this.hasIcon?h`<div class="icon-container"><slot name="icon"></slot></div>`:w}
          <div class="label-container">
            <span class="label">${this.label}</span>
            ${this.hasDescription?h`<span class="description">${this.description}</span>`:w}
          </div>
        </div>
        <div class="switch">
          <div class="presenter ${J({checked:this.checked})}">
            <div class="knob"></div>
            <input
              type="checkbox"
              .checked=${this.checked}
              ?disabled=${this.disabled}
              @input=${this._tryChange}
            />
          </div>
        </div>
        ${this.hasBottomDivider?h`<div class="bottom-divider"></div>`:w}
      </label>
    `}};Rr.styles=Q(cp);xo([l({type:String})],Rr.prototype,"label",2);xo([l({type:Boolean})],Rr.prototype,"checked",2);xo([l({type:Boolean})],Rr.prototype,"disabled",2);xo([l({type:Boolean})],Rr.prototype,"hasDescription",2);xo([l({type:String})],Rr.prototype,"description",2);xo([l({type:Boolean})],Rr.prototype,"hasBottomDivider",2);xo([l({type:Boolean})],Rr.prototype,"hasIcon",2);xo([l({type:Boolean})],Rr.prototype,"externalControl",2);Rr=xo([x("obc-toggle-switch")],Rr);var o9=Object.defineProperty;var i9=Object.getOwnPropertyDescriptor;var dp=(e,t,i,o)=>{var r=o>1?void 0:o?i9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)o9(t,i,r);return r};var Cl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
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
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Cl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;dp([l({type:Boolean})],Cl.prototype,"useCssColor",2);Cl=dp([x("obi-display-brilliance-low")],Cl);var a9=Object.defineProperty;var n9=Object.getOwnPropertyDescriptor;var pp=(e,t,i,o)=>{var r=o>1?void 0:o?n9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)a9(t,i,r);return r};var kl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.8331 9.17621C14.83 9.17312 14.8269 9.17002 14.8238 9.16694C14.1003 8.4458 13.1022 8 12 8C10.8978 8 9.89964 8.44583 9.17615 9.167C9.1731 9.17005 9.17005 9.1731 9.167 9.17615C8.44583 9.89964 8 10.8978 8 12C8 14.2091 9.79086 16 12 16C14.2091 16 16 14.2091 16 12C16 10.8978 15.5542 9.8997 14.8331 9.17621ZM12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14ZM18.364 4.22182L19.7782 5.63604L16.9497 8.46447L16.237 7.75175L15.5355 7.05025L18.364 4.22182ZM4.22183 5.63604L5.63605 4.22183L8.46447 7.05025L7.76316 7.75157L7.75175 7.76298L7.05026 8.46447L4.22183 5.63604ZM7.05025 15.5355L8.46446 16.9498L5.63603 19.7782L4.22182 18.364L7.05025 15.5355ZM16.9498 15.5355L19.7782 18.364L18.364 19.7782L15.5355 16.9497L16.9498 15.5355ZM11 2H13V6H11V2ZM2 13V11H6V13H2ZM13 22H11V18H13V22ZM22 11V13H18V11H22Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.8331 9.17621C14.83 9.17312 14.8269 9.17002 14.8238 9.16694C14.1003 8.4458 13.1022 8 12 8C10.8978 8 9.89964 8.44583 9.17615 9.167C9.1731 9.17005 9.17005 9.1731 9.167 9.17615C8.44583 9.89964 8 10.8978 8 12C8 14.2091 9.79086 16 12 16C14.2091 16 16 14.2091 16 12C16 10.8978 15.5542 9.8997 14.8331 9.17621ZM12 14C13.1046 14 14 13.1046 14 12C14 10.8954 13.1046 10 12 10C10.8954 10 10 10.8954 10 12C10 13.1046 10.8954 14 12 14ZM18.364 4.22182L19.7782 5.63604L16.9497 8.46447L16.237 7.75175L15.5355 7.05025L18.364 4.22182ZM4.22183 5.63604L5.63605 4.22183L8.46447 7.05025L7.76316 7.75157L7.75175 7.76298L7.05026 8.46447L4.22183 5.63604ZM7.05025 15.5355L8.46446 16.9498L5.63603 19.7782L4.22182 18.364L7.05025 15.5355ZM16.9498 15.5355L19.7782 18.364L18.364 19.7782L15.5355 16.9497L16.9498 15.5355ZM11 2H13V6H11V2ZM2 13V11H6V13H2ZM13 22H11V18H13V22ZM22 11V13H18V11H22Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};kl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;pp([l({type:Boolean})],kl.prototype,"useCssColor",2);kl=pp([x("obi-display-brilliance-proposal")],kl);var l9=Object.defineProperty;var s9=Object.getOwnPropertyDescriptor;var hp=(e,t,i,o)=>{var r=o>1?void 0:o?s9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)l9(t,i,r);return r};var Ll=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21C9.5 21 7.375 20.125 5.625 18.375C3.875 16.625 3 14.5 3 12C3 9.5 3.875 7.375 5.625 5.625C7.375 3.875 9.5 3 12 3C12.2333 3 12.4625 3.00833 12.6875 3.025C12.9125 3.04167 13.1333 3.06667 13.35 3.1C12.6667 3.58333 12.1208 4.2125 11.7125 4.9875C11.3042 5.7625 11.1 6.6 11.1 7.5C11.1 9 11.625 10.275 12.675 11.325C13.725 12.375 15 12.9 16.5 12.9C17.4167 12.9 18.2583 12.6958 19.025 12.2875C19.7917 11.8792 20.4167 11.3333 20.9 10.65C20.9333 10.8667 20.9583 11.0875 20.975 11.3125C20.9917 11.5375 21 11.7667 21 12C21 14.5 20.125 16.625 18.375 18.375C16.625 20.125 14.5 21 12 21ZM12 19C13.4667 19 14.7833 18.5958 15.95 17.7875C17.1167 16.9792 17.9667 15.925 18.5 14.625C18.1667 14.7083 17.8333 14.775 17.5 14.825C17.1667 14.875 16.8333 14.9 16.5 14.9C14.45 14.9 12.7042 14.1792 11.2625 12.7375C9.82083 11.2958 9.1 9.55 9.1 7.5C9.1 7.16667 9.125 6.83333 9.175 6.5C9.225 6.16667 9.29167 5.83333 9.375 5.5C8.075 6.03333 7.02083 6.88333 6.2125 8.05C5.40417 9.21667 5 10.5333 5 12C5 13.9333 5.68333 15.5833 7.05 16.95C8.41667 18.3167 10.0667 19 12 19Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21C9.5 21 7.375 20.125 5.625 18.375C3.875 16.625 3 14.5 3 12C3 9.5 3.875 7.375 5.625 5.625C7.375 3.875 9.5 3 12 3C12.2333 3 12.4625 3.00833 12.6875 3.025C12.9125 3.04167 13.1333 3.06667 13.35 3.1C12.6667 3.58333 12.1208 4.2125 11.7125 4.9875C11.3042 5.7625 11.1 6.6 11.1 7.5C11.1 9 11.625 10.275 12.675 11.325C13.725 12.375 15 12.9 16.5 12.9C17.4167 12.9 18.2583 12.6958 19.025 12.2875C19.7917 11.8792 20.4167 11.3333 20.9 10.65C20.9333 10.8667 20.9583 11.0875 20.975 11.3125C20.9917 11.5375 21 11.7667 21 12C21 14.5 20.125 16.625 18.375 18.375C16.625 20.125 14.5 21 12 21ZM12 19C13.4667 19 14.7833 18.5958 15.95 17.7875C17.1167 16.9792 17.9667 15.925 18.5 14.625C18.1667 14.7083 17.8333 14.775 17.5 14.825C17.1667 14.875 16.8333 14.9 16.5 14.9C14.45 14.9 12.7042 14.1792 11.2625 12.7375C9.82083 11.2958 9.1 9.55 9.1 7.5C9.1 7.16667 9.125 6.83333 9.175 6.5C9.225 6.16667 9.29167 5.83333 9.375 5.5C8.075 6.03333 7.02083 6.88333 6.2125 8.05C5.40417 9.21667 5 10.5333 5 12C5 13.9333 5.68333 15.5833 7.05 16.95C8.41667 18.3167 10.0667 19 12 19Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ll.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;hp([l({type:Boolean})],Ll.prototype,"useCssColor",2);Ll=hp([x("obi-palette-night")],Ll);var c9=Object.defineProperty;var d9=Object.getOwnPropertyDescriptor;var up=(e,t,i,o)=>{var r=o>1?void 0:o?d9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)c9(t,i,r);return r};var xl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.5529 3.75275C11.7695 3.24908 12.4805 3.24908 12.6971 3.75276L13.8662 6.47216C14.0151 6.81843 14.4328 6.95476 14.7559 6.76251L17.2931 5.2527C17.763 4.97306 18.3383 5.39286 18.2187 5.92818L17.5732 8.81846C17.491 9.18649 17.7491 9.5434 18.123 9.57861L21.0592 9.85509C21.603 9.9063 21.8228 10.5855 21.4128 10.948L19.1991 12.9052C19.1278 12.9683 19.0745 13.0436 19.0393 13.125H21C21.4142 13.125 21.75 13.4608 21.75 13.875C21.75 14.2892 21.4142 14.625 21 14.625H3C2.58579 14.625 2.25 14.2892 2.25 13.875C2.25 13.4608 2.58579 13.125 3 13.125H5.21069C5.17546 13.0436 5.12219 12.9683 5.05087 12.9052L2.83724 10.948C2.42724 10.5855 2.64697 9.9063 3.1908 9.85509L6.12699 9.57861C6.50087 9.5434 6.75903 9.18649 6.67683 8.81846L6.0313 5.92818C5.91173 5.39286 6.48698 4.97306 6.95691 5.2527L9.49414 6.76251C9.81722 6.95476 10.2349 6.81843 10.3838 6.47216L11.5529 3.75275ZM7.13114 13.125H17.1189C16.9886 10.4797 14.8026 8.375 12.125 8.375C9.44741 8.375 7.2614 10.4797 7.13114 13.125Z" fill="currentColor"/>
<path d="M7.5 15.75C7.08579 15.75 6.75 16.0858 6.75 16.5C6.75 16.9142 7.08579 17.25 7.5 17.25H16.5C16.9142 17.25 17.25 16.9142 17.25 16.5C17.25 16.0858 16.9142 15.75 16.5 15.75H7.5Z" fill="currentColor"/>
<path d="M13.875 19.25C13.875 19.6642 13.5392 20 13.125 20H12H10.875C10.4608 20 10.125 19.6642 10.125 19.25C10.125 18.8358 10.4608 18.5 10.875 18.5H12H13.125C13.5392 18.5 13.875 18.8358 13.875 19.25Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.5529 3.75275C11.7695 3.24908 12.4805 3.24908 12.6971 3.75276L13.8662 6.47216C14.0151 6.81843 14.4328 6.95476 14.7559 6.76251L17.2931 5.2527C17.763 4.97306 18.3383 5.39286 18.2187 5.92818L17.5732 8.81846C17.491 9.18649 17.7491 9.5434 18.123 9.57861L21.0592 9.85509C21.603 9.9063 21.8228 10.5855 21.4128 10.948L19.1991 12.9052C19.1278 12.9683 19.0745 13.0436 19.0393 13.125H21C21.4142 13.125 21.75 13.4608 21.75 13.875C21.75 14.2892 21.4142 14.625 21 14.625H3C2.58579 14.625 2.25 14.2892 2.25 13.875C2.25 13.4608 2.58579 13.125 3 13.125H5.21069C5.17546 13.0436 5.12219 12.9683 5.05087 12.9052L2.83724 10.948C2.42724 10.5855 2.64697 9.9063 3.1908 9.85509L6.12699 9.57861C6.50087 9.5434 6.75903 9.18649 6.67683 8.81846L6.0313 5.92818C5.91173 5.39286 6.48698 4.97306 6.95691 5.2527L9.49414 6.76251C9.81722 6.95476 10.2349 6.81843 10.3838 6.47216L11.5529 3.75275ZM7.13114 13.125H17.1189C16.9886 10.4797 14.8026 8.375 12.125 8.375C9.44741 8.375 7.2614 10.4797 7.13114 13.125Z" style="fill: var(--element-active-color)"/>
<path d="M7.5 15.75C7.08579 15.75 6.75 16.0858 6.75 16.5C6.75 16.9142 7.08579 17.25 7.5 17.25H16.5C16.9142 17.25 17.25 16.9142 17.25 16.5C17.25 16.0858 16.9142 15.75 16.5 15.75H7.5Z" style="fill: var(--element-active-color)"/>
<path d="M13.875 19.25C13.875 19.6642 13.5392 20 13.125 20H12H10.875C10.4608 20 10.125 19.6642 10.125 19.25C10.125 18.8358 10.4608 18.5 10.875 18.5H12H13.125C13.5392 18.5 13.875 18.8358 13.875 19.25Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};xl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;up([l({type:Boolean})],xl.prototype,"useCssColor",2);xl=up([x("obi-palette-dusk")],xl);var p9=Object.defineProperty;var h9=Object.getOwnPropertyDescriptor;var fp=(e,t,i,o)=>{var r=o>1?void 0:o?h9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)p9(t,i,r);return r};var $l=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.4178 2.66892C14.7789 2.25636 15.4554 2.47526 15.5064 3.02113L15.7816 5.96838C15.8166 6.34367 16.1721 6.60197 16.5386 6.51851L19.4174 5.8631C19.9506 5.74171 20.3687 6.3182 20.0902 6.79072L18.5862 9.34191C18.3947 9.66677 18.5305 10.0858 18.8753 10.2344L21.5838 11.4014C22.0855 11.6175 22.0854 12.3314 21.5838 12.5501L19.2437 13.5701C19.9738 14.2507 20.5123 15.1503 20.7626 16.1622C21.9582 16.6967 22.7499 17.9449 22.7499 19.3243C22.7499 21.1817 21.3013 22.75 19.4588 22.75H9.62935C8.73882 22.75 7.89257 22.3876 7.27532 21.7385C6.61858 21.085 6.27173 20.2054 6.25014 19.2667L6.24994 19.2581V19.212C6.24994 18.6736 6.37017 18.152 6.59526 17.6786L4.5824 18.1369C4.04921 18.2582 3.63113 17.6818 3.90968 17.2092L5.41363 14.658C5.60514 14.3332 5.46938 13.9141 5.12449 13.7655L2.41601 12.5986C1.91436 12.3825 1.9144 11.6686 2.41608 11.4499L5.12472 10.2692C5.46962 10.1189 5.60543 9.69915 5.41397 9.37526L3.91034 6.83168C3.63185 6.36057 4.05 5.78196 4.58318 5.90066L7.4619 6.54149C7.82846 6.62309 8.18396 6.36299 8.21905 5.98753L8.49462 3.03888C8.54566 2.49275 9.2222 2.27043 9.58323 2.68116L11.5324 4.89872C11.7807 5.18109 12.2201 5.17998 12.4683 4.89635L14.4178 2.66892ZM8.77567 15.8232C9.0014 15.7627 9.23504 15.7262 9.47374 15.7151C9.91656 15.02 10.6813 14.5702 11.5529 14.5702C11.6374 14.5702 11.7229 14.5744 11.8091 14.5835C12.7056 13.1529 14.2426 12.25 15.947 12.25C16.3039 12.25 16.652 12.29 16.9877 12.3658C17.1542 10.1198 15.7772 7.96694 13.5391 7.2428C10.9118 6.39271 8.09283 7.83343 7.24274 10.4608C6.59862 12.4515 7.26972 14.5523 8.77567 15.8232ZM12.8665 15.771C13.4558 14.5213 14.6481 13.75 15.947 13.75C17.6096 13.75 19.0881 15.057 19.371 16.8409L19.4468 17.3191L19.9138 17.4469C20.6575 17.6504 21.2499 18.4014 21.2499 19.3243C21.2499 20.4233 20.4045 21.25 19.4588 21.25H9.62935C9.14786 21.25 8.69223 21.0546 8.35732 20.6995L8.34813 20.6898L8.3386 20.6804C7.9796 20.326 7.7653 19.8279 7.74994 19.2403V19.212C7.74994 18.6904 7.94322 18.1961 8.2958 17.8083C8.65036 17.419 9.1208 17.2115 9.62936 17.2115C9.73976 17.2115 9.76618 17.213 9.79884 17.2188L10.4228 17.329L10.6357 16.7323C10.7806 16.3265 11.1414 16.0702 11.5529 16.0702C11.6726 16.0702 11.7795 16.0905 11.8851 16.1372L12.5544 16.4329L12.8665 15.771Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.4178 2.66892C14.7789 2.25636 15.4554 2.47526 15.5064 3.02113L15.7816 5.96838C15.8166 6.34367 16.1721 6.60197 16.5386 6.51851L19.4174 5.8631C19.9506 5.74171 20.3687 6.3182 20.0902 6.79072L18.5862 9.34191C18.3947 9.66677 18.5305 10.0858 18.8753 10.2344L21.5838 11.4014C22.0855 11.6175 22.0854 12.3314 21.5838 12.5501L19.2437 13.5701C19.9738 14.2507 20.5123 15.1503 20.7626 16.1622C21.9582 16.6967 22.7499 17.9449 22.7499 19.3243C22.7499 21.1817 21.3013 22.75 19.4588 22.75H9.62935C8.73882 22.75 7.89257 22.3876 7.27532 21.7385C6.61858 21.085 6.27173 20.2054 6.25014 19.2667L6.24994 19.2581V19.212C6.24994 18.6736 6.37017 18.152 6.59526 17.6786L4.5824 18.1369C4.04921 18.2582 3.63113 17.6818 3.90968 17.2092L5.41363 14.658C5.60514 14.3332 5.46938 13.9141 5.12449 13.7655L2.41601 12.5986C1.91436 12.3825 1.9144 11.6686 2.41608 11.4499L5.12472 10.2692C5.46962 10.1189 5.60543 9.69915 5.41397 9.37526L3.91034 6.83168C3.63185 6.36057 4.05 5.78196 4.58318 5.90066L7.4619 6.54149C7.82846 6.62309 8.18396 6.36299 8.21905 5.98753L8.49462 3.03888C8.54566 2.49275 9.2222 2.27043 9.58323 2.68116L11.5324 4.89872C11.7807 5.18109 12.2201 5.17998 12.4683 4.89635L14.4178 2.66892ZM8.77567 15.8232C9.0014 15.7627 9.23504 15.7262 9.47374 15.7151C9.91656 15.02 10.6813 14.5702 11.5529 14.5702C11.6374 14.5702 11.7229 14.5744 11.8091 14.5835C12.7056 13.1529 14.2426 12.25 15.947 12.25C16.3039 12.25 16.652 12.29 16.9877 12.3658C17.1542 10.1198 15.7772 7.96694 13.5391 7.2428C10.9118 6.39271 8.09283 7.83343 7.24274 10.4608C6.59862 12.4515 7.26972 14.5523 8.77567 15.8232ZM12.8665 15.771C13.4558 14.5213 14.6481 13.75 15.947 13.75C17.6096 13.75 19.0881 15.057 19.371 16.8409L19.4468 17.3191L19.9138 17.4469C20.6575 17.6504 21.2499 18.4014 21.2499 19.3243C21.2499 20.4233 20.4045 21.25 19.4588 21.25H9.62935C9.14786 21.25 8.69223 21.0546 8.35732 20.6995L8.34813 20.6898L8.3386 20.6804C7.9796 20.326 7.7653 19.8279 7.74994 19.2403V19.212C7.74994 18.6904 7.94322 18.1961 8.2958 17.8083C8.65036 17.419 9.1208 17.2115 9.62936 17.2115C9.73976 17.2115 9.76618 17.213 9.79884 17.2188L10.4228 17.329L10.6357 16.7323C10.7806 16.3265 11.1414 16.0702 11.5529 16.0702C11.6726 16.0702 11.7795 16.0905 11.8851 16.1372L12.5544 16.4329L12.8665 15.771Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};$l.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;fp([l({type:Boolean})],$l.prototype,"useCssColor",2);$l=fp([x("obi-palette-day")],$l);var u9=Object.defineProperty;var f9=Object.getOwnPropertyDescriptor;var vp=(e,t,i,o)=>{var r=o>1?void 0:o?f9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)u9(t,i,r);return r};var Ml=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.4279 2.37775C11.6445 1.87408 12.3555 1.87408 12.5721 2.37776L13.7412 5.09716C13.8901 5.44343 14.3078 5.57976 14.6309 5.38751L17.1681 3.8777C17.638 3.59806 18.2133 4.01786 18.0937 4.55318L17.4482 7.44346C17.366 7.81149 17.6241 8.1684 17.998 8.20361L20.9342 8.48009C21.478 8.5313 21.6978 9.21054 21.2878 9.57303L19.0741 11.5302C18.7923 11.7794 18.7923 12.2206 19.0741 12.4698L21.2878 14.427C21.6978 14.7895 21.478 15.4687 20.9342 15.5199L17.998 15.7964C17.6241 15.8316 17.366 16.1885 17.4482 16.5565L18.0937 19.4468C18.2133 19.9821 17.638 20.4019 17.1681 20.1223L14.6309 18.6125C14.3078 18.4202 13.8901 18.5566 13.7412 18.9028L12.5721 21.6222C12.3555 22.1259 11.6445 22.1259 11.4279 21.6222L10.2588 18.9028C10.1099 18.5566 9.69222 18.4202 9.36914 18.6125L6.83191 20.1223C6.36198 20.4019 5.78673 19.9821 5.9063 19.4468L6.55183 16.5565C6.63403 16.1885 6.37587 15.8316 6.00199 15.7964L3.06579 15.5199C2.52197 15.4687 2.30224 14.7895 2.71224 14.427L4.92587 12.4698C5.20775 12.2206 5.20774 11.7794 4.92587 11.5302L2.71224 9.57303C2.30224 9.21054 2.52197 8.5313 3.0658 8.48009L6.00199 8.20361C6.37587 8.1684 6.63403 7.81149 6.55183 7.44346L5.9063 4.55318C5.78673 4.01786 6.36198 3.59806 6.83191 3.8777L9.36914 5.38751C9.69222 5.57976 10.1099 5.44343 10.2588 5.09716L11.4279 2.37775ZM17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 9.23858 9.23858 7 12 7C14.7614 7 17 9.23858 17 12Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M11.4279 2.37775C11.6445 1.87408 12.3555 1.87408 12.5721 2.37776L13.7412 5.09716C13.8901 5.44343 14.3078 5.57976 14.6309 5.38751L17.1681 3.8777C17.638 3.59806 18.2133 4.01786 18.0937 4.55318L17.4482 7.44346C17.366 7.81149 17.6241 8.1684 17.998 8.20361L20.9342 8.48009C21.478 8.5313 21.6978 9.21054 21.2878 9.57303L19.0741 11.5302C18.7923 11.7794 18.7923 12.2206 19.0741 12.4698L21.2878 14.427C21.6978 14.7895 21.478 15.4687 20.9342 15.5199L17.998 15.7964C17.6241 15.8316 17.366 16.1885 17.4482 16.5565L18.0937 19.4468C18.2133 19.9821 17.638 20.4019 17.1681 20.1223L14.6309 18.6125C14.3078 18.4202 13.8901 18.5566 13.7412 18.9028L12.5721 21.6222C12.3555 22.1259 11.6445 22.1259 11.4279 21.6222L10.2588 18.9028C10.1099 18.5566 9.69222 18.4202 9.36914 18.6125L6.83191 20.1223C6.36198 20.4019 5.78673 19.9821 5.9063 19.4468L6.55183 16.5565C6.63403 16.1885 6.37587 15.8316 6.00199 15.7964L3.06579 15.5199C2.52197 15.4687 2.30224 14.7895 2.71224 14.427L4.92587 12.4698C5.20775 12.2206 5.20774 11.7794 4.92587 11.5302L2.71224 9.57303C2.30224 9.21054 2.52197 8.5313 3.0658 8.48009L6.00199 8.20361C6.37587 8.1684 6.63403 7.81149 6.55183 7.44346L5.9063 4.55318C5.78673 4.01786 6.36198 3.59806 6.83191 3.8777L9.36914 5.38751C9.69222 5.57976 10.1099 5.44343 10.2588 5.09716L11.4279 2.37775ZM17 12C17 14.7614 14.7614 17 12 17C9.23858 17 7 14.7614 7 12C7 9.23858 9.23858 7 12 7C14.7614 7 17 9.23858 17 12Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ml.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;vp([l({type:Boolean})],Ml.prototype,"useCssColor",2);Ml=vp([x("obi-palette-day-bright")],Ml);var v9=Object.defineProperty;var m9=Object.getOwnPropertyDescriptor;var mp=(e,t,i,o)=>{var r=o>1?void 0:o?m9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)v9(t,i,r);return r};var Hl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M7 15H11V17H7C4.24 17 2 14.76 2 12C2 9.24 4.24 7 7 7H11V9H7C5.35 9 4 10.35 4 12C4 13.65 5.35 15 7 15Z" fill="currentColor"/>
<path d="M13 7H17C19.76 7 22 9.24 22 12C22 14.76 19.76 17 17 17H13V15H17C18.65 15 20 13.65 20 12C20 10.35 18.65 9 17 9H13V7Z" fill="currentColor"/>
<path d="M16 11H8V13H16V11Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M7 15H11V17H7C4.24 17 2 14.76 2 12C2 9.24 4.24 7 7 7H11V9H7C5.35 9 4 10.35 4 12C4 13.65 5.35 15 7 15Z" style="fill: var(--element-active-color)"/>
<path d="M13 7H17C19.76 7 22 9.24 22 12C22 14.76 19.76 17 17 17H13V15H17C18.65 15 20 13.65 20 12C20 10.35 18.65 9 17 9H13V7Z" style="fill: var(--element-active-color)"/>
<path d="M16 11H8V13H16V11Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Hl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;mp([l({type:Boolean})],Hl.prototype,"useCssColor",2);Hl=mp([x("obi-link")],Hl);var g9=Object.defineProperty;var b9=Object.getOwnPropertyDescriptor;var gp=(e,t,i,o)=>{var r=o>1?void 0:o?b9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)g9(t,i,r);return r};var Sl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13.9999 18L15.4099 16.59L10.8299 12L15.4099 7.41L13.9999 6L7.99991 12L13.9999 18Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M13.9999 18L15.4099 16.59L10.8299 12L15.4099 7.41L13.9999 6L7.99991 12L13.9999 18Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Sl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;gp([l({type:Boolean})],Sl.prototype,"useCssColor",2);Sl=gp([x("obi-chevron-left-google")],Sl);var y9=Object.defineProperty;var w9=Object.getOwnPropertyDescriptor;var bp=(e,t,i,o)=>{var r=o>1?void 0:o?w9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)y9(t,i,r);return r};var _l=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M20 3H4C2.9 3 2 3.9 2 5V15C2 16.1 2.9 17 4 17H10V19H8V21H16V19H14V17H20C21.1 17 22 16.1 22 15V5C22 3.9 21.1 3 20 3ZM4 15H20V5H4V15Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M20 3H4C2.9 3 2 3.9 2 5V15C2 16.1 2.9 17 4 17H10V19H8V21H16V19H14V17H20C21.1 17 22 16.1 22 15V5C22 3.9 21.1 3 20 3ZM4 15H20V5H4V15Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};_l.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;bp([l({type:Boolean})],_l.prototype,"useCssColor",2);_l=bp([x("obi-screen-desk")],_l);var Vl="lit-localize-status";var yp=e=>typeof e!=="string"&&"strTag"in e;var L1=(e,t,i)=>{let o=e[0];for(let r=1;r<e.length;r++){o+=t[i?i[r-1]:r-1];o+=e[r]}return o};var Al=(e=>yp(e)?L1(e.strings,e.values):e);var jt=Al;var x1=class{constructor(t){this.__litLocalizeEventHandler=i=>{if(i.detail.status==="ready"){this.host.requestUpdate()}};this.host=t}hostConnected(){window.addEventListener(Vl,this.__litLocalizeEventHandler)}hostDisconnected(){window.removeEventListener(Vl,this.__litLocalizeEventHandler)}};var C9=e=>e.addController(new x1(e));var wp=C9;var Cp=()=>(e,t)=>{e.addInitializer(wp);return e};var Zl=class{constructor(){this.settled=false;this.promise=new Promise((t,i)=>{this._resolve=t;this._reject=i})}resolve(t){this.settled=true;this._resolve(t)}reject(t){this.settled=true;this._reject(t)}};var k9=[];for(let e=0;e<256;e++){k9[e]=(e>>4&15).toString(16)+(e&15).toString(16)}var x9=new Zl;x9.resolve();var kp=L`
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
`;var $9=Object.defineProperty;var M9=Object.getOwnPropertyDescriptor;var Tl=(e,t,i,o)=>{var r=o>1?void 0:o?M9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)$9(t,i,r);return r};var ha=class extends k{constructor(){super(...arguments);this.totalSteps=5;this.currentStep=1;this.fullwidth=false}get validCurrentStep(){return Math.max(1,Math.min(this.currentStep,this.totalSteps))}get validTotalSteps(){return Math.max(1,this.totalSteps)}renderDots(){const e=[];for(let t=0;t<this.validTotalSteps;t++){e.push(h`
        <div
          class=${J({dot:true,"state-active":t===this.validCurrentStep-1,"state-inactive":t!==this.validCurrentStep-1})}
        ></div>
      `)}return e}render(){return h`
      <div
        class=${J({wrapper:true,"style-fullwidth":this.fullwidth,"style-compact":!this.fullwidth})}
      >
        <div class="content-container">${this.renderDots()}</div>
      </div>
    `}};ha.styles=Q(kp);Tl([l({type:Number})],ha.prototype,"totalSteps",2);Tl([l({type:Number})],ha.prototype,"currentStep",2);Tl([l({type:Boolean})],ha.prototype,"fullwidth",2);ha=Tl([x("obc-progress-indicator-dots")],ha);var Lp=L`
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
`;var H9=Object.defineProperty;var S9=Object.getOwnPropertyDescriptor;var xp=(e,t,i,o)=>{var r=o>1?void 0:o?S9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)H9(t,i,r);return r};var Pl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M9.5 15.0687C9.5 15.6745 9.5 15.9774 9.6198 16.1177C9.72374 16.2394 9.87967 16.304 10.0392 16.2914C10.2231 16.2769 10.4373 16.0627 10.8657 15.6344L13.9343 12.5657C14.1323 12.3677 14.2313 12.2687 14.2684 12.1546C14.3011 12.0541 14.3011 11.946 14.2684 11.8455C14.2313 11.7314 14.1323 11.6324 13.9343 11.4344L10.8657 8.36573C10.4373 7.93736 10.2231 7.72317 10.0392 7.7087C9.87967 7.69614 9.72374 7.76073 9.6198 7.88243C9.5 8.0227 9.5 8.3256 9.5 8.93142L9.5 15.0687Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M9.5 15.0687C9.5 15.6745 9.5 15.9774 9.6198 16.1177C9.72374 16.2394 9.87967 16.304 10.0392 16.2914C10.2231 16.2769 10.4373 16.0627 10.8657 15.6344L13.9343 12.5657C14.1323 12.3677 14.2313 12.2687 14.2684 12.1546C14.3011 12.0541 14.3011 11.946 14.2684 11.8455C14.2313 11.7314 14.1323 11.6324 13.9343 11.4344L10.8657 8.36573C10.4373 7.93736 10.2231 7.72317 10.0392 7.7087C9.87967 7.69614 9.72374 7.76073 9.6198 7.88243C9.5 8.0227 9.5 8.3256 9.5 8.93142L9.5 15.0687Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Pl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;xp([l({type:Boolean})],Pl.prototype,"useCssColor",2);Pl=xp([x("obi-arrow-flyout-google")],Pl);var $p=L`
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
`;var _9=Object.defineProperty;var V9=Object.getOwnPropertyDescriptor;var en=(e,t,i,o)=>{var r=o>1?void 0:o?V9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)_9(t,i,r);return r};var ki=(e=>{e["Full"]="full";e["IconOnly"]="icon-only";e["IconOnlyLarge"]="icon-only-large";e["Compact"]="compact";return e})(ki||{});var Ci=class extends k{constructor(){super(...arguments);this.variant="full";this.flyoutVariant="full";this.smallScreen=false;this.slotObservers=[];this.hasFooter=false}findAllElements(e,t,{slot:i,stopTag:o}={}){const r=[];for(const a of e.children){if(a.tagName.toLowerCase()===t){if(i&&a.getAttribute("slot")!==i){continue}r.push(a)}else if(o&&a.tagName.toLowerCase()===o){continue}else{if(i&&a.getAttribute("slot")!==i){continue}r.push(...this.findAllElements(a,t,{stopTag:o}))}}return r}findAllGroups(e){return this.findAllElements(e,"obc-navigation-item-group")}findRootItems(e){return this.findAllElements(e,"obc-navigation-item",{stopTag:"obc-navigation-item-group"})}findAllItems(e,t){return this.findAllElements(e,"obc-navigation-item",{slot:t})}closeAllGroups(){const e=this.findAllGroups(this);e.forEach(t=>{t.close()})}registerGroup(e){e.forEach(t=>{t.addEventListener("open",()=>{e.forEach(o=>{if(o!==t){o.close()}})});const i=this.findAllGroups(t);this.registerGroup(i)})}cleanupSlotObservers(){this.slotObservers.forEach(e=>e.disconnect());this.slotObservers=[]}setupSlotObservers(){this.cleanupSlotObservers();const e=this.shadowRoot?.querySelector('slot[name="main"]');const t=this.shadowRoot?.querySelector('slot[name="footer"]');this.hasFooter=t?.assignedElements().length>0;[e,t].forEach(i=>{if(i){const o=i.assignedElements();o.forEach(r=>{const a=new MutationObserver(()=>{this.setupItems()});a.observe(r,{childList:true,subtree:true});this.slotObservers.push(a)})}})}firstUpdated(e){super.firstUpdated(e);const t=this.findAllGroups(this);this.registerGroup(t)}updated(e){super.updated(e);if(e.has("variant")||e.has("flyoutVariant")){this.setupItems()}}setVariantToFlyoutItems(e){const t=this.findAllElements(e,"obc-navigation-item");t.forEach(o=>{o.variant="full"});const i=this.findAllGroups(e);i.forEach(o=>{o.variant="full";this.setVariantToFlyoutItems(o)})}disconnectedCallback(){super.disconnectedCallback();this.cleanupSlotObservers()}handleSlotChange(){this.setupItems();this.setupSlotObservers()}setupItems(){const e=this.variant!=="full"||this.flyoutVariant==="compact";this.setHugToGroups(this,e);const t=this.findAllGroups(this);t.forEach(o=>{o.variant=this.variant;this.setVariantToFlyoutItems(o)});this.findRootItems(this).forEach(o=>{o.variant=this.variant});const i=this.smallScreen&&this.variant==="full"?"compact":this.variant;this.findAllItems(this,"footer").forEach(o=>{o.variant=i});this.findAllItems(this,"logo").forEach(o=>{o.variant=i});this.findAllItems(this).forEach(o=>{o.addEventListener("click",()=>{this.closeAllGroups()})})}setHugToGroups(e,t){const i=this.findAllGroups(e);i.forEach(o=>{o.hug=t;this.setHugToGroups(o,t)})}render(){return h`
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
              ${this.smallScreen?h` <slot name="logo"></slot> `:w}
            </ol>
          </nav>
          ${this.smallScreen?w:h`
                <div class="logo">
                  <slot name="logo"></slot>
                </div>
              `}
        </div>
      </div>
    `}};Ci.styles=Q($p);en([l({type:String})],Ci.prototype,"variant",2);en([l({type:String})],Ci.prototype,"flyoutVariant",2);en([l({type:Boolean})],Ci.prototype,"smallScreen",2);en([Ve()],Ci.prototype,"hasFooter",2);Ci=en([x("obc-navigation-menu")],Ci);var A9=Object.defineProperty;var Z9=Object.getOwnPropertyDescriptor;var $o=(e,t,i,o)=>{var r=o>1?void 0:o?Z9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)A9(t,i,r);return r};var Ir=class extends k{constructor(){super(...arguments);this.label="Label";this.checked=false;this.variant=ki.Full;this.group=false;this.groupSelected=false;this.hasIcon=false;this.hasTrailingIcon=false}onClick(){dispatchEvent(new CustomEvent("click"))}render(){const e=this.group&&this.variant!==ki.IconOnly;const t=this.variant===ki.Compact;return h`
      <a
        class="${J({wrapper:true,checked:this.checked,"group-selected":this.groupSelected&&this.group,"has-icon":this.hasIcon,[this.variant]:true})}"
        href=${$e(this.href)}
        @click=${this.onClick}
      >
        <div class="visible-wrapper">
          ${this.hasIcon?h`<slot name="icon" class="icon leading"></slot>`:w}
          ${![ki.IconOnly,ki.IconOnlyLarge].includes(this.variant)?h`
                <span
                  part="label"
                  class=${J({label:true,"label-flyout":e&&!t})}
                >
                  ${this.label}
                </span>
              `:w}
          ${e?h`
                <div class="flyout-wrapper">
                  <obi-arrow-flyout-google
                    class="icon trailing"
                  ></obi-arrow-flyout-google>
                </div>
              `:w}
          ${this.hasTrailingIcon&&!e?h`<slot name="trailing-icon" class="icon trailing"></slot>`:w}
        </div>
      </a>
    `}};Ir.styles=Q(Lp);$o([l({type:String})],Ir.prototype,"label",2);$o([l({type:String})],Ir.prototype,"href",2);$o([l({type:Boolean})],Ir.prototype,"checked",2);$o([l({type:String})],Ir.prototype,"variant",2);$o([l({type:Boolean})],Ir.prototype,"group",2);$o([l({type:Boolean})],Ir.prototype,"groupSelected",2);$o([l({type:Boolean,reflect:true})],Ir.prototype,"hasIcon",2);$o([l({type:Boolean})],Ir.prototype,"hasTrailingIcon",2);Ir=$o([x("obc-navigation-item")],Ir);var Mp=L`
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
`;var T9=Object.defineProperty;var P9=Object.getOwnPropertyDescriptor;var Li=(e,t,i,o)=>{var r=o>1?void 0:o?P9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)T9(t,i,r);return r};var Mo=class extends k{constructor(){super(...arguments);this.label="Button";this.checked=false;this.showLabel=true;this.integration=false;this.size="normal";this.disabled=false}render(){return h` <button
      class="${J({wrapper:true,checked:this.checked,small:this.size==="small",integration:this.integration,disabled:this.disabled})}"
      ?disabled=${this.disabled}
    >
      <div class="icon-wrapper">
        <span class="icon">
          <slot name="icon"></slot>
        </span>
      </div>
      ${this.showLabel?h`<div class="label">${this.label}</div>`:w}
    </button>`}};Mo.styles=Q(Mp);Li([l({type:String})],Mo.prototype,"label",2);Li([l({type:Boolean})],Mo.prototype,"checked",2);Li([l({type:Boolean,attribute:false})],Mo.prototype,"showLabel",2);Li([l({type:Boolean})],Mo.prototype,"integration",2);Li([l({type:String})],Mo.prototype,"size",2);Li([l({type:Boolean})],Mo.prototype,"disabled",2);Mo=Li([x("obc-app-button")],Mo);var Hp=L`
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
`;var z9=Object.defineProperty;var B9=Object.getOwnPropertyDescriptor;var Fo=(e,t,i,o)=>{var r=o>1?void 0:o?B9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)z9(t,i,r);return r};var so=class extends k{constructor(){super(...arguments);this.variant="icon";this.size="regular";this.styleType="flat";this.static=false;this.disabled=false;this.initials=""}get formattedInitials(){if(!this.initials)return"";const e=this.initials.replace(/\s+/g,"").toUpperCase();const t=this.size==="large"?3:2;if(e.length>t){console.warn(`Initials "${this.initials}" are longer than ${t} characters.`);return e.slice(0,t)}return e}get shouldShowIcon(){return this.variant==="icon"}render(){const e=this.size==="large"&&this.styleType==="flat"?"normal":this.styleType;const t={wrapper:true,"wrapper-static":this.static,[`style-${e}`]:true,"mode-icon":this.shouldShowIcon,"mode-initials":!this.shouldShowIcon,"state-static":this.static,[`size-${this.size}`]:true};const i=this.static?We`div`:We`button`;const o=this.label&&!this.static?ce`<span class="user-label" part="label">${this.label}</span>`:w;return ce`
        <${i}
          class=${J(t)}
          ?disabled=${this.disabled}
          aria-label=${this.initials||"User button"}
        >
        <div class="content-container" part="content-container">
          <div class="user-button-circle">
            ${this.shouldShowIcon?ce`
                    <div class="icon-container">
                      <slot name="icon">
                        <!-- Fallback to default icon if no slot content -->
                        <obi-user></obi-user>
                      </slot>
                    </div>
                  `:ce`
                    <span class="user-initials">
                      ${this.formattedInitials}
                    </span>
                  `}
          </div>
          ${o}
        </div>
        </${i}>
      `}};so.styles=Q(Hp);Fo([l({type:String})],so.prototype,"variant",2);Fo([l({type:String})],so.prototype,"size",2);Fo([l({type:String})],so.prototype,"styleType",2);Fo([l({type:Boolean})],so.prototype,"static",2);Fo([l({type:Boolean})],so.prototype,"disabled",2);Fo([l({type:String})],so.prototype,"initials",2);Fo([l({type:String})],so.prototype,"label",2);so=Fo([x("obc-user-button")],so);var Sp=L`
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
`;var O9=Object.defineProperty;var D9=Object.getOwnPropertyDescriptor;var tn=(e,t,i,o)=>{var r=o>1?void 0:o?D9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)O9(t,i,r);return r};var xi=class extends k{constructor(){super(...arguments);this.nTabs=1;this.selectedTab=0;this.hasDefaultSlotOnly=false;this.hasTabIcons=false}_handleKeyDown(e){const t=e.target;if(!t.classList.contains("tab-button"))return;const i=this.selectedTab;switch(e.key){case"ArrowRight":this.setSelectedTab((i+1)%this.nTabs);break;case"ArrowLeft":this.setSelectedTab((i-1+this.nTabs)%this.nTabs);break;case"Home":this.setSelectedTab(0);break;case"End":this.setSelectedTab(this.nTabs-1);break;default:return}e.preventDefault();this._focusTab(this.selectedTab)}setSelectedTab(e){this.selectedTab=e;this.dispatchEvent(new CustomEvent("tab-change",{detail:{tab:e}}))}_focusTab(e){const t=this.shadowRoot?.querySelector(`button[data-index="${e}"]`);t?.focus()}_generateTabHeaders(){return[...Array(this.nTabs)].map((e,t)=>{const i=t!==this.nTabs-1&&this.selectedTab!==t&&t+1!==this.selectedTab;const o=this.hasTabIcons?h`<span class="tab-icon">
            <slot name="tab-icon-${t}"></slot>
          </span>`:w;return h`
        <button
          class="tab-button ${i?"has-divider":""}"
          role="tab"
          aria-selected="${this.selectedTab===t}"
          aria-controls="panel-${t}"
          id="tab-${t}"
          data-index="${t}"
          tabindex="${this.selectedTab===t?0:-1}"
          @click="${()=>this.setSelectedTab(t)}"
          @focus="${()=>this.setSelectedTab(t)}"
        >
          <div class="tab-title-container">
            ${o}
            <slot class="tab-title" name="tab-title-${t}"
              >Tab ${t+1}</slot
            >
          </div>
        </button>
      `})}_generateTabPanels(){if(this.hasDefaultSlotOnly){return h`<div
        role="tabpanel"
        class="tab-content"
        id="panel-${this.selectedTab}"
        aria-labelledby="tab-${this.selectedTab}"
        tabindex="0"
      >
        <slot></slot>
      </div>`}return[...Array(this.nTabs)].map((e,t)=>h`
        <div
          role="tabpanel"
          id="panel-${t}"
          aria-labelledby="tab-${t}"
          tabindex="0"
          ?hidden="${this.selectedTab!==t}"
        >
          <slot name="tab-content-${t}"></slot>
        </div>
      `)}render(){return h`
      <div class="tab-container" @keydown="${this._handleKeyDown}">
        <div class="tab-header" role="tablist" aria-label="Tab List">
          ${this._generateTabHeaders()}
        </div>
        <div class="tab-panels">${this._generateTabPanels()}</div>
      </div>
    `}};xi.styles=Q(Sp);tn([l({type:Number})],xi.prototype,"nTabs",2);tn([l({type:Number})],xi.prototype,"selectedTab",2);tn([l({type:Boolean})],xi.prototype,"hasDefaultSlotOnly",2);tn([l({type:Boolean})],xi.prototype,"hasTabIcons",2);xi=tn([x("obc-tabbed-card")],xi);var E9=Object.defineProperty;var R9=Object.getOwnPropertyDescriptor;var _p=(e,t,i,o)=>{var r=o>1?void 0:o?R9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)E9(t,i,r);return r};var zl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
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
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};zl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;_p([l({type:Boolean})],zl.prototype,"useCssColor",2);zl=_p([x("obi-display-brilliance-iec")],zl);var I9=Object.defineProperty;var N9=Object.getOwnPropertyDescriptor;var Lt=(e,t,i,o)=>{var r=o>1?void 0:o?N9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)I9(t,i,r);return r};var nt=class extends k{constructor(){super(...arguments);this.palette="day";this.brightness=50;this.showLinkBrightness=false;this.showLinkPalette=false;this.showBrightness=true;this.showPalette=true;this.showNightPalette=true;this.showDuskPalette=true;this.showDayPalette=true;this.showBrightPalette=true;this.variant="normal";this.brightnessUnit="%";this.brightnessMax=100;this.brightnessMinorStep=5;this.brightnessMajorStep=25;this.brightnessInputVariant="buttons";this.showScreenControlLink=false}willUpdate(e){if(this.showPalette){const t=this.availablePalettes;if(t.length>0&&!t.includes(this.palette)){this.palette=t[0];this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}}))}}}onPaletteChanged(e){this.palette=e.detail.value;this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:e.detail.value}}))}handleBrightnessChanged(e){this.brightness=e.detail;this.dispatchEvent(new CustomEvent("brightness-changed",{detail:{value:e.detail}}))}increaseBrightness(e){this.brightness=Math.max(0,Math.min(this.brightness+e,this.brightnessMax));this.dispatchEvent(new CustomEvent("brightness-changed",{detail:{value:this.brightness}}))}get canIncreaseBrightness(){return this.brightness<this.brightnessMax}get canDecreaseBrightness(){return this.brightness>0}onLinkPaletteChanged(e){this.dispatchEvent(new CustomEvent("link-palette-changed",{detail:{value:e.target.checked}}))}onLinkBrightnessChanged(e){this.dispatchEvent(new CustomEvent("link-brightness-changed",{detail:{value:e.target.checked}}))}get availablePalettes(){const e=[];if(this.showNightPalette)e.push("night");if(this.showDuskPalette)e.push("dusk");if(this.showDayPalette)e.push("day");if(this.showBrightPalette)e.push("bright");return e}get canIncreasePalette(){const e=this.availablePalettes;const t=e.indexOf(this.palette);return t>=0&&t<e.length-1}get canDecreasePalette(){const e=this.availablePalettes;const t=e.indexOf(this.palette);return t>0}nextPalette(){if(this.canIncreasePalette){const e=this.availablePalettes;const t=e.indexOf(this.palette);this.palette=e[t+1];this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}}))}}previousPalette(){if(this.canDecreasePalette){const e=this.availablePalettes;const t=e.indexOf(this.palette);this.palette=e[t-1];this.dispatchEvent(new CustomEvent("palette-changed",{detail:{value:this.palette}}))}}renderBrightness(){const e=this.variant==="tabbed"?w:h`<div class="title-container">
            <h3>${jt("Brilliance")}</h3>
          </div>`;const t=this.brightness.toString().length+.5*this.brightnessUnit.length;return h`${e}
      <div class="content-container brilliance">
        ${this.variant==="compact"?h` <obc-slider
              value=${this.brightness}
              @value=${this.handleBrightnessChanged}
              min="0"
              max=${this.brightnessMax}
              variant=${Ja.Normal}
              haslefticon
              hasrighticon
            >
              <obi-display-brilliance-low
                slot="icon-left"
              ></obi-display-brilliance-low>
              <obi-display-brilliance-proposal
                slot="icon-right"
              ></obi-display-brilliance-proposal>
            </obc-slider>`:h`
              <div class="value-container">
                <div class="value-label-container">
                  <obi-display-brilliance-proposal
                    class="icon"
                  ></obi-display-brilliance-proposal>
                  <div class="label-container" style="width: ${t}ch">
                    <div class="value">${this.brightness.toFixed(0)}</div>
                    <div class="unit">${this.brightnessUnit}</div>
                  </div>
                </div>
                <div class="value-slider-container">
                  ${this.brightnessInputVariant==="buttons"?h`
                        <obc-slider
                          value=${this.brightness}
                          variant=${Ja.NoInput}
                          min="0"
                          max=${this.brightnessMax}
                        ></obc-slider>
                      `:h`
                        <obc-slider
                          value=${this.brightness}
                          variant=${Ja.Enhanced}
                          @value=${this.handleBrightnessChanged}
                          min="0"
                          max=${this.brightnessMax}
                        ></obc-slider>
                      `}
                </div>
              </div>
              ${this.brightnessInputVariant==="buttons"?h`
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
                  `:w}
            `}
        ${this.showLinkBrightness?h`<obc-toggle-switch
              .label="${jt("Link")}"
              hasicon
              @input=${this.onLinkBrightnessChanged}
            >
              <obi-link slot="icon"></obi-link>
            </obc-toggle-switch>`:w}
      </div>`}get effectivePalette(){const e=this.availablePalettes;return e.includes(this.palette)?this.palette:e[0]}get paletteIcon(){if(this.effectivePalette==="night"){return h`<obi-palette-night class="icon"></obi-palette-night>`}else if(this.effectivePalette==="dusk"){return h`<obi-palette-dusk class="icon"></obi-palette-dusk>`}else if(this.effectivePalette==="day"){return h`<obi-palette-day class="icon"></obi-palette-day>`}else if(this.effectivePalette==="bright"){return h`<obi-palette-day-bright
        class="icon"
      ></obi-palette-day-bright>`}else{return w}}paletteOptions(){const e=[];if(this.showNightPalette)e.push(h`<obc-toggle-button-option value="night" type="icon">
          <obi-palette-night slot="icon"></obi-palette-night>
        </obc-toggle-button-option>`);if(this.showDuskPalette)e.push(h`<obc-toggle-button-option value="dusk" type="icon">
          <obi-palette-dusk slot="icon"></obi-palette-dusk>
        </obc-toggle-button-option>`);if(this.showDayPalette)e.push(h`<obc-toggle-button-option value="day" type="icon">
          <obi-palette-day slot="icon"></obi-palette-day>
        </obc-toggle-button-option>`);if(this.showBrightPalette)e.push(h`<obc-toggle-button-option value="bright" type="icon">
          <obi-palette-day-bright slot="icon"></obi-palette-day-bright>
        </obc-toggle-button-option>`);return e}renderPalette(){const e=this.availablePalettes;if(e.length===0)return w;const t={["night"]:jt("Night"),["dusk"]:jt("Dusk"),["day"]:jt("Day"),["bright"]:jt("Bright")};const i=t[this.effectivePalette];const o=i.length;const r=e.indexOf(this.effectivePalette);const a=Math.min(r+1,e.length-1);const n=Math.max(r-1,0);const p=t[e[a]];const d=t[e[n]];return h`
      ${this.variant==="tabbed"?w:h`
            <div class="title-container">
              <h3>${jt("Day")}/${jt("Night")}</h3>
            </div>
          `}
      <div
        class="content-container palette ${this.showLinkPalette?"with-link":"without-link"}"
      >
        ${this.variant==="compact"?h` <obc-toggle-button-group
              value=${this.effectivePalette}
              @value=${this.onPaletteChanged}
              variant=${wi.regular}
              type=${pa.icon}
            >
              ${this.paletteOptions()}
            </obc-toggle-button-group>`:h`
              <div class="value-container">
                <div class="value-label-container">
                  ${this.paletteIcon}
                  <div class="label-container" style="width: ${o}ch">
                    <div class="value">${i}</div>
                  </div>
                </div>
                <obc-progress-indicator-dots
                  .totalSteps=${e.length}
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
                  ${d}
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
                  ${p}
                  <obi-chevron-right-google
                    slot="trailing-icon"
                  ></obi-chevron-right-google>
                </obc-button>
              </div>
            `}
        ${this.showLinkPalette?h`<obc-toggle-switch
              .label="${jt("Link")}"
              hasicon
              @input=${this.onLinkPaletteChanged}
            >
              <obi-link slot="icon"></obi-link>
            </obc-toggle-switch>`:w}
      </div>
    `}renderScreenControlLink(){if(!this.showScreenControlLink){return w}return h`
      <div class="footer">
        <obc-navigation-item
          .label="${jt("Screen Control")}"
          @click=${()=>this.handleScreenControlLinkClicked()}
          hasicon
        >
          <obc-user-button slot="icon" static variant="icon" styleType="normal">
            <obi-screen-desk slot="icon"></obi-screen-desk>
          </obc-user-button>
        </obc-navigation-item>
      </div>
    `}render(){if(this.variant==="tabbed"){return h`<obc-tabbed-card class="card" nTabs=${2} hasTabIcons>
        <span slot="tab-title-0">${jt("Brilliance")}</span>
        <obi-display-brilliance-iec
          slot="tab-icon-0"
        ></obi-display-brilliance-iec>
        <span slot="tab-title-1">${jt("Day")}/${jt("Night")}</span>
        <obi-palette-day-night-iec
          slot="tab-icon-1"
        ></obi-palette-day-night-iec>
        <div slot="tab-content-0">
          ${this.renderBrightness()} ${this.renderScreenControlLink()}
        </div>
        <div slot="tab-content-1">
          ${this.renderPalette()} ${this.renderScreenControlLink()}
        </div>
      </obc-tabbed-card>`}else{return h`
        <div class="card ${this.variant}">
          ${this.showBrightness?this.renderBrightness():w}
          ${this.showBrightness&&this.showPalette?h`<div class="divider"></div>`:w}
          ${this.showPalette?this.renderPalette():w}
          ${this.renderScreenControlLink()}
        </div>
      `}}handleScreenControlLinkClicked(){this.dispatchEvent(new CustomEvent("screen-control-link-clicked"))}};nt.styles=Q(lp);Lt([l({type:String})],nt.prototype,"palette",2);Lt([l({type:Number})],nt.prototype,"brightness",2);Lt([l({type:Boolean})],nt.prototype,"showLinkBrightness",2);Lt([l({type:Boolean})],nt.prototype,"showLinkPalette",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showBrightness",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showPalette",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showNightPalette",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showDuskPalette",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showDayPalette",2);Lt([l({type:Boolean,attribute:false})],nt.prototype,"showBrightPalette",2);Lt([l({type:String})],nt.prototype,"variant",2);Lt([l({type:String})],nt.prototype,"brightnessUnit",2);Lt([l({type:Number})],nt.prototype,"brightnessMax",2);Lt([l({type:Number})],nt.prototype,"brightnessMinorStep",2);Lt([l({type:Number})],nt.prototype,"brightnessMajorStep",2);Lt([l({type:String})],nt.prototype,"brightnessInputVariant",2);Lt([l({type:Boolean})],nt.prototype,"showScreenControlLink",2);nt=Lt([Cp(),x("obc-brilliance-menu")],nt);var Vp=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.wrapper {
  position: relative;
  user-select: none;
  padding: 0;
  background: transparent;
  width: fit-content;
  height: var(--ui-components-button-touch-target-size);
  appearance: none;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-button-font-weight);
  font-size: var(--global-typography-ui-button-font-size);
  line-height: var(--global-typography-ui-button-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.wrapper.full-width {
    width: 100%;
  }

.wrapper.full-width .visible-wrapper {
      width: 100%;
      justify-content: space-between;
    }

.wrapper .visible-wrapper {
    height: var(--ui-components-button-visual-size);
    border-radius: var(--ui-components-button-border-radius-top-left)
      var(--ui-components-button-border-radius-top-right)
      var(--ui-components-button-border-radius-bottom-right)
      var(--ui-components-button-border-radius-bottom-left);
    display: flex;
    align-items: center;
    justify-content: center;
    padding-left: calc(var(--ui-components-button-padding-horizontal) * 2);
    padding-right: var(--ui-components-button-padding-horizontal);
  }

.wrapper .icon-container {
    display: flex;
    align-items: center;
    justify-content: center;
    height: var(--global-size-spacing-icon-icon-size-regular);
    width: var(--global-size-spacing-icon-icon-size-regular);
  }

.wrapper .icon {
    height: var(--global-size-spacing-icon-icon-size-regular);
    width: var(--global-size-spacing-icon-icon-size-regular);
  }

.wrapper.disabled .icon-container {
    color: var(--on-normal-disabled-color);
  }

.wrapper.disabled .icon {
    color: var(--on-normal-disabled-color);
  }

.wrapper .label {
    padding-left: var(--ui-components-button-label-spacing);
    padding-right: var(--ui-components-button-label-spacing);
    text-overflow: ellipsis;
    white-space: nowrap;
    overflow: hidden;
  }

.wrapper {
            cursor: pointer;
}

.wrapper:focus {
            outline: none;
}

.wrapper .visible-wrapper {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper.activated .visible-wrapper {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.wrapper:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper:active .visible-wrapper {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.wrapper:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper:disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.disabled .visible-wrapper {
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
  color: var(--on-normal-active-color);
}

.wrapper .icon {
    color: var(--on-normal-neutral-color);
  }

.wrapper:disabled .icon {
    color: var(--on-normal-disabled-color);
  }

.wrapper select {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    appearance: none;
    appearance: base-select;
    opacity: 0;
  }

.wrapper:has(select:focus-visible) .visible-wrapper {
  outline-color: var(--border-focus-color);
  outline-width: var(--global-size-spacing-border-weight-focusframe);
  outline-style: solid;
  border-color: var(--container-global-color);
  z-index: 1;
}

::picker(select) {
  appearance: base-select;
  border: none;
  min-width: var(--ui-components-context-menu-menu-width);
  border-radius: 12px;
  background: var(--container-global-color);
  box-shadow: var(--shadow-floating);
  padding: var(--ui-components-context-menu-margin-vertical)
    var(--ui-components-context-menu-margin-horizontal);

  overflow-y: auto;
}

.wrapper.open-top select::picker(select) {
  position-area: block-start span-inline-end;
}

option {
  height: var(--menu-navigation-components-navigation-item-touch-target-size);
  min-height: var(
    --menu-navigation-components-navigation-item-touch-target-size
  );
  padding: 0px
    var(--menu-navigation-components-navigation-item-padding-horizontal);
  border-radius: var(
    --menu-navigation-components-navigation-item-border-radius
  );
}

option {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

option:focus {
            outline: none;
}

option.activated {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

option:hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

option:active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

option:focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

option:disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

option.disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

option {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-neutral-color);
}

option:checked {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

option:checked:focus {
            outline: none;
}

option.activated:checked {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

option:checked:hover {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

option:checked:active {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

option:checked:focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

option:checked:disabled {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

option.disabled:checked {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

option:checked {
  color: var(--on-flat-active-color);
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

option::checkmark {
  display: none;
}

.wrapper.flat {
            cursor: pointer;
}

.wrapper.flat:focus {
            outline: none;
}

.wrapper.flat .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.flat.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.flat:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.flat:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.flat:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.flat:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.flat.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.flat:disabled {
            cursor: not-allowed;
}

.wrapper.flat.disabled {
            cursor: not-allowed;
}

.wrapper.integration {
            cursor: pointer;
}

.wrapper.integration:focus {
            outline: none;
}

.wrapper.integration .visible-wrapper {
            border-color: var(--integration-selected-enabled-border-color);
            background-color: var(--integration-selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--integration-selected-enabled-border-color);
            --base-background-color: var(--integration-selected-enabled-background-color);
}

.wrapper.integration.activated .visible-wrapper {
            border-color: var(--integration-selected-activated-border-color);
            background-color: var(--integration-selected-activated-background-color);
            --base-border-color: var(--integration-selected-activated-border-color);
            --base-background-color: var(--integration-selected-activated-background-color);
}

@media (hover:hover) {

.wrapper.integration:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--integration-selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--integration-selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.integration:active .visible-wrapper {
            border-color: var(--integration-selected-pressed-border-color);
            background-color: var(--integration-selected-pressed-background-color);
}

.wrapper.integration:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.integration:disabled .visible-wrapper {
            border-color: var(--integration-selected-disabled-border-color);
            background-color: var(--integration-selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-selected-disabled-color) !important;
}

.wrapper.integration.disabled .visible-wrapper {
            border-color: var(--integration-selected-disabled-border-color);
            background-color: var(--integration-selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--integration-on-selected-disabled-color) !important;
}

.wrapper.integration:disabled {
            cursor: not-allowed;
}

.wrapper.integration.disabled {
            cursor: not-allowed;
}

.wrapper.integration .visible-wrapper {
    box-sizing: border-box;
    height: 40px;
  }
`;var j9=Object.defineProperty;var F9=Object.getOwnPropertyDescriptor;var Ap=(e,t,i,o)=>{var r=o>1?void 0:o?F9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)j9(t,i,r);return r};var Bl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8.9313 10C8.32548 10 8.02257 10 7.88231 10.1198C7.76061 10.2237 7.69602 10.3797 7.70858 10.5392C7.72305 10.7231 7.93724 10.9373 8.36561 11.3657L11.4342 14.4343C11.6323 14.6323 11.7313 14.7313 11.8454 14.7684C11.9458 14.8011 12.054 14.8011 12.1544 14.7684C12.2686 14.7313 12.3676 14.6323 12.5656 14.4343L15.6342 11.3657C16.0626 10.9373 16.2768 10.7231 16.2913 10.5392C16.3038 10.3797 16.2392 10.2237 16.1175 10.1198C15.9773 10 15.6744 10 15.0686 10H8.9313Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.9313 10C8.32548 10 8.02257 10 7.88231 10.1198C7.76061 10.2237 7.69602 10.3797 7.70858 10.5392C7.72305 10.7231 7.93724 10.9373 8.36561 11.3657L11.4342 14.4343C11.6323 14.6323 11.7313 14.7313 11.8454 14.7684C11.9458 14.8011 12.054 14.8011 12.1544 14.7684C12.2686 14.7313 12.3676 14.6323 12.5656 14.4343L15.6342 11.3657C16.0626 10.9373 16.2768 10.7231 16.2913 10.5392C16.3038 10.3797 16.2392 10.2237 16.1175 10.1198C15.9773 10 15.6744 10 15.0686 10H8.9313Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Bl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ap([l({type:Boolean})],Bl.prototype,"useCssColor",2);Bl=Ap([x("obi-drop-down-google")],Bl);var U9=Object.defineProperty;var W9=Object.getOwnPropertyDescriptor;var Nr=(e,t,i,o)=>{var r=o>1?void 0:o?W9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)U9(t,i,r);return r};var lr=class extends k{constructor(){super(...arguments);this.options=[];this.disabled=false;this.fullWidth=false;this.type="label";this.openTop=false;this.integration=false;this.flat=false;this.selectedValue="";this.selectedLabel=""}connectedCallback(){super.connectedCallback();this.updateSelectedValues()}willUpdate(e){if(e.has("value")||e.has("options")){this.updateSelectedValues()}}updateSelectedValues(){if(this.options.length===0){this.selectedValue="";this.selectedLabel="";return}this.selectedValue=this.value||this.options[0].value;this.selectedLabel=this.value?this.options.find(e=>e.value===this.value)?.label||"":this.options[0].label}render(){return h`
      <div
        class=${J({wrapper:true,"full-width":this.fullWidth,"open-top":this.openTop,integration:this.integration,flat:this.flat&&!this.integration,disabled:this.disabled})}
      >
        <div class="visible-wrapper">
          ${this.type!=="label"?h`<div class="icon-container"><slot name="icon"></slot></div>`:w}
          ${this.type!=="icon"?h`<div class="label">${this.selectedLabel}</div>`:w}
          <div class="icon">
            <obi-drop-down-google></obi-drop-down-google>
          </div>
        </div>
        <select @change=${this.changeHandler} ?disabled=${this.disabled}>
          ${this.options.map(e=>{const t=e.level?(e.level-1)*2:0;const i=[];for(let o=0;o<t;o++){i.push(h`&nbsp;`)}return h`<option
              value=${e.value}
              ?selected=${e.value===this.selectedValue}
            >
              ${i}${e.label}
            </option>`})}
        </select>
      </div>
    `}changeHandler(e){const t=e.target;this.selectedValue=t.value;this.selectedLabel=this.options.find(i=>i.value===this.selectedValue).label.trim();this.dispatchEvent(new CustomEvent("dropdown-change",{detail:{value:this.selectedValue,label:this.selectedLabel}}));this.dispatchEvent(new CustomEvent("change",{detail:{value:this.selectedValue,label:this.selectedLabel}}))}};lr.styles=Q(Vp);Nr([l({type:Array})],lr.prototype,"options",2);Nr([l({type:String})],lr.prototype,"value",2);Nr([l({type:Boolean})],lr.prototype,"disabled",2);Nr([l({type:Boolean})],lr.prototype,"fullWidth",2);Nr([l({type:String})],lr.prototype,"type",2);Nr([l({type:Boolean})],lr.prototype,"openTop",2);Nr([l({type:Boolean})],lr.prototype,"integration",2);Nr([l({type:Boolean})],lr.prototype,"flat",2);Nr([Ve()],lr.prototype,"selectedValue",2);Nr([Ve()],lr.prototype,"selectedLabel",2);lr=Nr([x("obc-dropdown-button")],lr);var Zp=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: block;
  width: 100%;
  border-radius: 4px;
}

.wrapper {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  width: 100%;
  user-select: none;
}

.title-container {
  display: flex;
  align-items: center;
  width: 100%;
  padding: 4px var(--app-components-system-menu-padding-horizontal, 8px);
  box-sizing: border-box;
  background: var(--container-section-color);
  border-top: 1px solid var(--border-outline-color);
  border-bottom: 1px solid var(--border-outline-color);
}

.label-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-left: var(--app-components-system-menu-padding-horizontal, 8px);
  padding-right: var(--app-components-system-menu-padding-horizontal, 8px);
}

.label {
  display: flex;
  align-items: flex-start;
  gap: var(--menu-navigation-components-appointment-item-label-spacing, 8px);
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-neutral-color);
}

.day-container {
  display: flex;
  align-items: center;
}

.date-container {
  display: flex;
  align-items: center;
  gap: 4px;
}

.content-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  width: 100%;
  padding-left: var(
    --menu-navigation-components-appointment-item-padding-horizontal,
    8px
  );
  padding-right: var(
    --menu-navigation-components-appointment-item-padding-horizontal,
    8px
  );
  box-sizing: border-box;
}

.event-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  width: calc(100% + 8px);
  margin-left: -4px;
  padding: 4px;
  box-sizing: border-box;
}
`;var Tp=(e,t,i)=>{const o=new Map;for(let r=t;r<=i;r++)o.set(e[r],r);return o};var rn=wo(class extends to{constructor(e){if(super(e),e.type!==Eo.CHILD)throw Error("repeat() can only be used in text expressions")}dt(e,t,i){let o;void 0===i?i=t:void 0!==t&&(o=t);const r=[],a=[];let n=0;for(const p of e)r[n]=o?o(p,n):n,a[n]=i(p,n),n++;return{values:a,keys:r}}render(e,t,i){return this.dt(e,t,i).values}update(e,[t,i,o]){const r=Jd(e),{values:a,keys:n}=this.dt(t,i,o);if(!Array.isArray(r))return this.ut=n,a;const p=this.ut??=[],d=[];let f,g,m=0,u=r.length-1,M=0,C=a.length-1;for(;m<=u&&M<=C;)if(null===r[m])m++;else if(null===r[u])u--;else if(p[m]===n[M])d[M]=jo(r[m],a[M]),m++,M++;else if(p[u]===n[C])d[C]=jo(r[u],a[C]),u--,C--;else if(p[m]===n[C])d[C]=jo(r[m],a[C]),na(e,d[C+1],r[m]),m++,C--;else if(p[u]===n[M])d[M]=jo(r[u],a[M]),na(e,r[m],r[u]),u--,M++;else if(void 0===f&&(f=Tp(n,M,C),g=Tp(p,m,u)),f.has(p[m]))if(f.has(p[u])){const A=g.get(n[M]),H=void 0!==A?r[A]:null;if(null===H){const _=na(e,r[m]);jo(_,a[M]),d[M]=_}else d[M]=jo(H,a[M]),na(e,r[m],H),r[A]=null;M++}else dl(r[u]),u--;else dl(r[m]),m++;for(;M<=C;){const A=na(e,d[C+1]);jo(A,a[M]),d[M++]=A}for(;m<=u;){const A=r[m++];null!==A&&dl(A)}return this.ut=n,Xd(e,d),ar}});var Pp=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: block;
  width: 100%;
  min-width: 0;
}

.wrapper {
  display: flex;
  align-self: stretch;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  width: 100%;
  user-select: none;
  border-radius: var(
    --menu-navigation-components-appointment-item-border-radius,
    6px
  );
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

.wrapper:focus-visible {
    outline: 2px solid var(--instrument-frame-tertiary-color, #0066cc);
    outline-offset: 2px;
  }

/* Keyboard press visual feedback - matches :active state from mixin */

.wrapper.pressing .visible-wrapper {
    background-color: var(--flat-pressed-background-color);
    border-color: var(--flat-pressed-border-color);
  }

.wrapper .visible-wrapper {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex: 1 0 0;
    min-width: 0;
    text-align: left;
    gap: var(--menu-navigation-components-appointment-item-label-spacing, 8px);
    padding: var(
        --menu-navigation-components-appointment-item-padding-vertical,
        4px
      )
      0 var(--menu-navigation-components-appointment-item-padding-vertical, 4px)
      var(--menu-navigation-components-appointment-item-padding-horizontal, 8px);
    border-radius: var(
      --menu-navigation-components-appointment-item-border-radius,
      6px
    );
    min-height: 48px;
    box-sizing: border-box;
    position: relative;
    overflow: hidden;
  }

.wrapper.type-color-coded:not(:hover):not(:active) .visible-wrapper {
      background: var(--Color-Base-Categorical-50, #e4eefd);
      border: 1px solid var(--Color-Base-Categorical-100, #cadefc);
    }

.wrapper.disabled {
    cursor: not-allowed;
  }

.wrapper.disabled .title,.wrapper.disabled .time-container,.wrapper.disabled .description {
      color: var(--on-flat-disabled-color);
    }

.event-content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  flex: 1 0 0;
  min-width: 0;
}

.time-container {
  display: flex;
  align-items: center;
  gap: 2px;
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-neutral-color);
}

.time {
  white-space: pre-wrap;
}

.time-separator {
  flex-shrink: 0;
}

.label-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  align-self: stretch;
  min-width: 0;
  padding-right: var(
    --menu-navigation-components-appointment-item-padding-horizontal,
    8px
  );
}

.title-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  align-self: stretch;
  min-width: 0;
}

.title {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-active-color);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.description-container {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  align-self: stretch;
  min-width: 0;
}

.description {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--on-flat-neutral-color);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.arrow {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  color: var(--on-flat-neutral-color);
}
`;var G9=Object.defineProperty;var q9=Object.getOwnPropertyDescriptor;var sr=(e,t,i,o)=>{var r=o>1?void 0:o?q9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)G9(t,i,r);return r};var $1=(e=>{e["SingleLine"]="singleLine";e["DoubleLine"]="doubleLine";e["Aggregated"]="aggregated";return e})($1||{});var Ft=class extends k{constructor(){super(...arguments);this.title="";this.description="";this.startTime="";this.endTime="";this.eventItemType="singleLine";this.hasArrow=false;this.hasTime=false;this.hasEndTime=false;this.aggregatedCount=0;this.colorCoded=false;this.disabled=false;this._pressing=false}_handleClick(e){e.stopPropagation();this.dispatchEvent(new CustomEvent("event-click",{bubbles:true,composed:true,detail:{title:this.title,startTime:this.startTime,endTime:this.endTime}}))}_getAggregatedText(){const e=this.aggregatedCount??0;return e===1?"1 more event":`${e} more events`}_handleKeyDown(e){if(e.key==="Enter"||e.key===" "){e.stopPropagation();this._pressing=true;setTimeout(()=>{this._pressing=false},150)}}render(){const e=this.eventItemType==="aggregated";const t=this.eventItemType==="doubleLine";const i=this.colorCoded;return h`
      <button
        type="button"
        @click=${this._handleClick}
        @keydown=${this._handleKeyDown}
        class=${J({wrapper:true,"type-aggregated":e,"type-double-line":t,"type-color-coded":i,disabled:this.disabled,pressing:this._pressing})}
        ?disabled=${this.disabled}
      >
        <div class="visible-wrapper">
          <div class="event-content">
            ${this.hasTime&&this.startTime?h`
                  <div class="time-container">
                    <span class="time">${this.startTime}</span>
                    ${this.hasEndTime&&this.endTime?h`
                          <span class="time-separator">–</span>
                          <span class="time">${this.endTime}</span>
                        `:w}
                  </div>
                `:w}
            <div class="label-container">
              <div class="title-container">
                <p class="title">
                  ${e?this._getAggregatedText():this.title}
                </p>
              </div>
              ${t&&this.description?h`
                    <div class="description-container">
                      <p class="description">${this.description}</p>
                    </div>
                  `:w}
            </div>
          </div>
          ${this.hasArrow?h`<div class="arrow">
                <obi-arrow-flyout-google></obi-arrow-flyout-google>
              </div>`:w}
        </div>
      </button>
    `}};Ft.styles=Q(Pp);sr([l({type:String})],Ft.prototype,"title",2);sr([l({type:String})],Ft.prototype,"description",2);sr([l({type:String})],Ft.prototype,"startTime",2);sr([l({type:String})],Ft.prototype,"endTime",2);sr([l({type:String})],Ft.prototype,"eventItemType",2);sr([l({type:Boolean})],Ft.prototype,"hasArrow",2);sr([l({type:Boolean})],Ft.prototype,"hasTime",2);sr([l({type:Boolean})],Ft.prototype,"hasEndTime",2);sr([l({type:Number})],Ft.prototype,"aggregatedCount",2);sr([l({type:Boolean})],Ft.prototype,"colorCoded",2);sr([l({type:Boolean})],Ft.prototype,"disabled",2);sr([Ve()],Ft.prototype,"_pressing",2);Ft=sr([x("obc-event-item")],Ft);var Y9=Object.defineProperty;var Q9=Object.getOwnPropertyDescriptor;var on=(e,t,i,o)=>{var r=o>1?void 0:o?Q9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Y9(t,i,r);return r};var $i=class extends k{constructor(){super(...arguments);this.showHeader=true;this.date=new Date;this.events=[]}get _normalizedDate(){if(this.date instanceof Date){return this.date}return new Date(this.date)}get _dayName(){return this._normalizedDate.toLocaleDateString(this.locale,{weekday:"long"})}get _monthName(){return this._normalizedDate.toLocaleDateString(this.locale,{month:"short"})}get _dateNumber(){return this._normalizedDate.getDate().toString()}get _year(){return this._normalizedDate.getFullYear().toString()}render(){return h`
      <div class="wrapper">
        ${this.showHeader?h`
              <div class="title-container">
                <div class="label-container">
                  <div class="label">
                    <span class="day-container">
                      <span class="day">${this._dayName}</span>
                      <span class="comma">,</span>
                    </span>
                    <span class="date-container">
                      <span>${this._dateNumber}</span>
                      <span class="month">${this._monthName}</span>
                    </span>
                    <span class="year">${this._year}</span>
                  </div>
                </div>
              </div>
            `:w}
        <div class="content-container">
          <div class="event-container" role="list" aria-label="Events">
            ${rn(this.events,(e,t)=>`${e.title}-${e.startTime}-${e.endTime}-${t}`,e=>h`
                <obc-event-item
                  role="listitem"
                  .title=${e.title}
                  .description=${e.description??""}
                  .startTime=${e.startTime}
                  .endTime=${e.endTime}
                  .eventItemType=${e.eventItemType??$1.SingleLine}
                  .hasArrow=${e.hasArrow??false}
                  .hasTime=${e.hasTime??false}
                  .hasEndTime=${e.hasEndTime??false}
                  .aggregatedCount=${e.aggregatedCount??0}
                  .colorCoded=${e.colorCoded??false}
                  .disabled=${e.disabled??false}
                ></obc-event-item>
              `)}
          </div>
        </div>
      </div>
    `}};$i.styles=Q(Zp);on([l({type:Boolean,attribute:false})],$i.prototype,"showHeader",2);on([l({attribute:false})],$i.prototype,"date",2);on([l({attribute:false})],$i.prototype,"events",2);on([l({type:String})],$i.prototype,"locale",2);$i=on([x("obc-event-list")],$i);var zp=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  display: block;
  user-select: none;
}

.grid-container {
  display: grid;
  height: 100%;
  grid-template-columns: repeat(var(--grid-columns), auto);
  align-content: start;
  grid-template-rows: min-content min-content 1fr;
}

.grid-container.has-selection-column {
    grid-template-columns:
      var(
        --selection-column-width,
        var(--menu-navigation-components-table-item-touch-target-size)
      )
      repeat(var(--grid-columns-rest), minmax(0, 1fr));
  }

.grid-container .grid-header {
    grid-row: 1;
    display: grid;
    grid-column: 1/-1;
    grid-template-columns: subgrid;
    padding: 0 var(--menu-navigation-components-table-header-row-margin);
  }

.grid-container .grid-header .selection-header {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    min-width: var(
      --selection-column-width,
      var(--menu-navigation-components-table-item-touch-target-size)
    );
    min-height: var(
      --menu-navigation-components-table-header-item-touch-target-size
    );
  }

.grid-container .grid-header-divider {
    grid-row: 2;
    grid-column: 1/-1;
    margin: 0 8px;
    border-bottom: 1px solid var(--border-divider-color);
  }

.grid-container .grid-column-divider {
    grid-row: 1/-1;
    width: 1px;
    background: var(--border-divider-color);
    height: 100%;
    right: 0;
    margin-left: auto;
    z-index: 1;
    pointer-events: none;
  }

.grid-container {

  --offset: calc(
    (
        var(--obc-scrollbar-touch-target-size) -
          var(--obc-scrollbar-visual-target-size)
      ) /
      2
  );
}

.grid-container ::-webkit-scrollbar {
    width: var(--obc-scrollbar-touch-target-size);
    height: var(--obc-scrollbar-touch-target-size);
  }

.grid-container ::-webkit-scrollbar-track-piece {
    border: var(--offset) solid transparent;
    border-radius: 9999px;
    background-color: var(--indent-enabled-background-color);
    margin-top: calc(-1 * var(--offset));
    margin-bottom: calc(-1 * var(--offset));
    box-sizing: border-box;
    background-clip: content-box;
  }

.grid-container ::-webkit-scrollbar-track-piece:vertical:start {
    border-bottom-width: 0;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }

.grid-container ::-webkit-scrollbar-track-piece:vertical:end {
    border-top-width: 0;
    border-top-left-radius: 0;
    border-top-right-radius: 0;
  }

.grid-container ::-webkit-scrollbar-track-piece:hover {
    outline-color: var(--indent-hover-border-color);
    background-color: var(--indent-hover-background-color);
  }

.grid-container ::-webkit-scrollbar-track-piece:active {
    outline-color: var(--indent-pressed-border-color);
    background-color: var(--indent-pressed-background-color);
  }

.grid-container ::-webkit-scrollbar-thumb {
    border: calc(var(--offset) + 1px) solid transparent;
    outline: 1px solid var(--obc-scrollbar-thumb-border-color);
    outline-offset: calc(-1 * var(--offset) - 1px);
    background-clip: content-box;
    border-radius: 9999px;
    background-color: var(--obc-scrollbar-thumb-background-color);
    min-height: calc(var(--obc-scrollbar-touch-target-size) * 1.5);
  }

.grid-container ::-webkit-scrollbar-thumb:hover {
    outline-color: var(--obc-scrollbar-thumb-hover-border-color);
    background-color: var(--obc-scrollbar-thumb-hover-background-color);
  }

.grid-container ::-webkit-scrollbar-thumb:active {
    outline-color: var(--obc-scrollbar-thumb-active-border-color);
    background-color: var(--obc-scrollbar-thumb-active-background-color);
  }

.grid-container ::-webkit-scrollbar-button:start:decrement,.grid-container ::-webkit-scrollbar-button:end:increment {
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

.grid-container ::-webkit-scrollbar-button:start:decrement:hover,.grid-container ::-webkit-scrollbar-button:end:increment:hover {
    background-color: var(--flat-hover-background-color);
  }

.grid-container ::-webkit-scrollbar-button:start:decrement:active,.grid-container ::-webkit-scrollbar-button:end:increment:active {
    background-color: var(--flat-pressed-background-color);
  }

.grid-container ::-webkit-scrollbar-button:vertical:start:decrement {
    background-image: var(--icon-02-chevron-up);
  }

.grid-container ::-webkit-scrollbar-button:vertical:end:increment {
    background-image: var(--icon-02-chevron-down);
  }

.grid-container .grid-body {
    grid-row: 3;
    overflow: auto;
    scrollbar-gutter: stable;
    display: grid;
    grid-column: 1/-1;
    grid-template-columns: subgrid;
    padding: 0 var(--menu-navigation-components-table-header-row-margin);
  }

.grid-container .grid-row {
    display: grid;
    grid-column: 1/-1;
    grid-template-columns: subgrid;
    min-height: var(--menu-navigation-components-table-item-touch-target-size);
    will-change: transform, opacity;
    position: relative;
    padding: 0;
  }

.striped:is(.grid-container .grid-row) {
      background: var(--container-section-color);
    }

:is(.grid-container .grid-row) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

:is(.grid-container .grid-row):focus {
            outline: none;
}

.activated:is(.grid-container .grid-row) {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

:is(.grid-container .grid-row):hover {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.grid-container .grid-row):active {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

:is(.grid-container .grid-row):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.grid-container .grid-row):disabled {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.disabled:is(.grid-container .grid-row) {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.grid-container .grid-row {
    border: 1px solid transparent;
    --flat-active-background-color: transparent;
  }

:is(.grid-container .grid-row):focus-visible {
    outline-offset: -2px;
  }

.grid-container .grid-row {
    border-radius: var(--global-border-radius-border-radius-base);
  }

.selected:is(.grid-container .grid-row) {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

.selected:is(.grid-container .grid-row):focus {
            outline: none;
}

.selected.activated:is(.grid-container .grid-row) {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

.selected:is(.grid-container .grid-row):hover {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.selected:is(.grid-container .grid-row):active {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

.selected:is(.grid-container .grid-row):focus-visible {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.selected:is(.grid-container .grid-row):disabled {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.selected.disabled:is(.grid-container .grid-row) {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.selected-with-prev:is(.grid-container .grid-row) {
      border-top-color: transparent;
      border-top-left-radius: 0;
      border-top-right-radius: 0;
    }

.selected-with-next:is(.grid-container .grid-row) {
      border-bottom-color: transparent;
      border-bottom-left-radius: 0;
      border-bottom-right-radius: 0;
    }

.selected-with-next:is(.grid-container .grid-row) .grid-row-divider {
      display: none;
    }

.animating:is(.grid-container .grid-row) {
      pointer-events: none;
    }

:is(.grid-container .grid-row) .grid-cell {
      position: relative;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      padding: 0 var(--menu-navigation-components-table-item-padding-horizontal);
      min-height: 100%;
      min-width: var(--menu-navigation-components-table-item-touch-target-size);
      gap: var(--menu-navigation-components-table-item-label-spacing);
      font-family: var(--font-family-main);
      font-weight: var(--global-typography-ui-body-font-weight);
      font-size: var(--global-typography-ui-body-font-size);
      line-height: var(--global-typography-ui-body-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      color: var(--on-flat-active-color);
    }

.selection:is(:is(.grid-container .grid-row) .grid-cell) {
        min-width: var(
          --selection-column-width,
          var(--menu-navigation-components-table-item-touch-target-size)
        );
        width: var(
          --selection-column-width,
          var(--menu-navigation-components-table-item-touch-target-size)
        );
        max-width: var(
          --selection-column-width,
          var(--menu-navigation-components-table-item-touch-target-size)
        );
        padding: 0;
      }

.neutral:is(:is(.grid-container .grid-row) .grid-cell) {
        color: var(--on-flat-neutral-color);
      }

.vertical:is(:is(.grid-container .grid-row) .grid-cell) {
        flex-direction: column;
        align-items: flex-start;
        justify-content: flex-start;
        gap: 0;
        padding-top: var(--menu-navigation-components-table-item-label-spacing);
        padding-bottom: var(
          --menu-navigation-components-table-item-label-spacing
        );
      }

.align-center:is(:is(.grid-container .grid-row) .grid-cell) {
        justify-content: center;
      }

.align-right:is(:is(.grid-container .grid-row) .grid-cell) {
        justify-content: flex-end;
      }

.align-left:is(:is(.grid-container .grid-row) .grid-cell) {
        justify-content: flex-start;
      }

.no-wrap:is(:is(.grid-container .grid-row) .grid-cell) > * {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

.no-wrap:is(:is(.grid-container .grid-row) .grid-cell) {
        width: 100%;
      }

.no-wrap:is(:is(.grid-container .grid-row) .grid-cell) .title {
          flex-shrink: 0;
        }

.no-wrap:is(:is(.grid-container .grid-row) .grid-cell) .text {
          flex-shrink: 10000;
        }

:is(:is(.grid-container .grid-row) .grid-cell) .icon {
        width: var(--menu-navigation-components-table-item-icon-size);
        height: var(--menu-navigation-components-table-item-icon-size);
        flex-shrink: 0;
      }

.large-icon:is(:is(.grid-container .grid-row) .grid-cell) .icon {
        min-width: var(--menu-navigation-components-table-item-icon-size-large);
        min-height: var(
          --menu-navigation-components-table-item-icon-size-large
        );
        width: fit-content;
        height: fit-content;
        display: grid;
      }

:is(:is(.grid-container .grid-row) .grid-cell) .title {
        font-family: var(--font-family-main);
        font-weight: var(--font-weight-bold);
        font-size: var(--global-typography-ui-body-active-font-size);
        line-height: var(--global-typography-ui-body-active-line-height);
        font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      }

.button:is(:is(.grid-container .grid-row) .grid-cell) obc-button {
          width: 100%;
        }

.checkbox:is(:is(.grid-container .grid-row) .grid-cell) {
        min-width: 0;
      }

.checkbox:is(:is(.grid-container .grid-row) .grid-cell) {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
        background: transparent;
        --flat-active-background-color: transparent;
        --flat-hover-background-color: transparent;
}

.horizontal-bar:is(:is(.grid-container .grid-row) .grid-cell) {
        padding: 0
          var(--menu-navigation-components-table-item-padding-horizontal);
      }

.horizontal-bar:is(:is(.grid-container .grid-row) .grid-cell) obc-bar-horizontal {
        display: block;
        width: 100%;
        height: 100%;
      }

.tags:is(:is(.grid-container .grid-row) .grid-cell) {
        gap: calc(
          var(--menu-navigation-components-table-item-badge-spacing) * 2
        );
      }

.tags:is(:is(.grid-container .grid-row) .grid-cell) .tag-overflow {
          font-family: var(--font-family-main);
          font-weight: var(--font-weight-regular);
          font-size: var(--global-typography-ui-label-font-size);
          line-height: var(--global-typography-ui-label-line-height);
          font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
          color: var(--on-flat-neutral-color);
          white-space: nowrap;
          margin: 0;
        }

.tags.wrap:is(:is(.grid-container .grid-row) .grid-cell) {
          flex-wrap: wrap;
          align-content: center;
        }

.grid-container .grid-row-divider {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    margin: 0 8px;
    border-radius: 100px;
    background: var(--border-divider-color);
    height: 1px;
    margin-bottom: -1.5px;
    z-index: -1;
  }
`;var Bp=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  display: flex;
  width: 100%;
}

.wrapper {
  width: 100%;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: stretch;
  user-select: none;
  -webkit-user-select: none;
  appearance: none;
  border: none;
  background: transparent;
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-semibold);
  font-size: var(--global-typography-ui-overline-font-size);
  line-height: var(--global-typography-ui-overline-line-height);
  letter-spacing: var(--global-typography-ui-overline-letter-spacing);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  height: var(--menu-navigation-components-table-header-item-touch-target-size);
  padding: 0
    var(--menu-navigation-components-table-header-item-margin-horizontal);

  color: var(--element-neutral-color);
}

.wrapper.sortable {
            cursor: pointer;
}

.wrapper.sortable:focus {
            outline: none;
}

.wrapper.sortable .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.sortable.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.sortable:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.sortable:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.sortable:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.sortable:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.sortable.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.sortable:disabled {
            cursor: not-allowed;
}

.wrapper.sortable.disabled {
            cursor: not-allowed;
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
  color: var(--instrument-enhanced-secondary-color);
}

.wrapper.style-narrow {
  padding: 0;
  height: var(--menu-navigation-components-table-header-item-icon-size);
}

.wrapper.style-narrow .visible-wrapper {
    border-radius: 0;
    border-width: 0;
    min-height: var(--menu-navigation-components-table-header-item-icon-size);
  }

.wrapper .visible-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: var(
    --menu-navigation-components-table-header-item-visual-target-size
  );
  border-radius: var(
    --menu-navigation-components-table-header-item-border-radius
  );
  padding: 0
    var(--menu-navigation-components-table-header-item-padding-horizontal);
}

.wrapper .label {
  padding: 0 var(--menu-navigation-components-table-header-item-label-spacing);
  white-space: nowrap;
  flex-grow: 1;
  text-align: var(--menu-navigation-components-table-header-item-label-align, left);
}

/* Icon containers */

.wrapper .leading,
.wrapper .trailing,
.wrapper .sort-icon {
  display: inline-flex;
  align-items: center;
}

.wrapper.has-leading-icon .leading,
.wrapper .sort-icon {
  width: var(--menu-navigation-components-table-header-item-icon-size);
  height: var(--menu-navigation-components-table-header-item-icon-size);
}

/* Disabled text color alignment */

.wrapper:disabled .label,
.wrapper.disabled .label {
  color: var(--element-disabled-color);
}

.divider {
  display: flex;
  height: 24px;
  align-items: center;
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  margin: auto;
  width: 1px;
  background-color: var(--border-divider-color);
}
`;var K9=Object.defineProperty;var X9=Object.getOwnPropertyDescriptor;var Op=(e,t,i,o)=>{var r=o>1?void 0:o?X9(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)K9(t,i,r);return r};var Ol=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6 14.0002L7.41 15.4102L12 10.8302L16.59 15.4102L18 14.0002L12 8.00016L6 14.0002Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M6 14.0002L7.41 15.4102L12 10.8302L16.59 15.4102L18 14.0002L12 8.00016L6 14.0002Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ol.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Op([l({type:Boolean})],Ol.prototype,"useCssColor",2);Ol=Op([x("obi-chevron-up-google")],Ol);var J9=Object.defineProperty;var e7=Object.getOwnPropertyDescriptor;var Dp=(e,t,i,o)=>{var r=o>1?void 0:o?e7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)J9(t,i,r);return r};var Dl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M18 9.41L16.59 8L12 12.58L7.41 8L6 9.41L12 15.41L18 9.41Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M18 9.41L16.59 8L12 12.58L7.41 8L6 9.41L12 15.41L18 9.41Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Dl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Dp([l({type:Boolean})],Dl.prototype,"useCssColor",2);Dl=Dp([x("obi-chevron-down-google")],Dl);var t7=Object.defineProperty;var r7=Object.getOwnPropertyDescriptor;var Uo=(e,t,i,o)=>{var r=o>1?void 0:o?r7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)t7(t,i,r);return r};var El=(e=>{e["Regular"]="Regular";e["IconOnly"]="IconOnly";e["Narrow"]="Narrow";return e})(El||{});var co=class extends k{constructor(){super(...arguments);this.type="Regular";this.disabled=false;this.hasLeadingIcon=false;this.sortDirection="none";this.showDivider=false;this.checked=false;this.sortable=false}render(){const e={wrapper:true,[`style-${(this.type??"Regular").toLowerCase()}`]:true,sortable:this.sortable,disabled:this.disabled,"has-leading-icon":this.hasLeadingIcon,"sorted-asc":this.sortDirection==="asc","sorted-desc":this.sortDirection==="desc",checked:this.checked};const t=this.sortable?We`button`:We`div`;return ce`
      <${t}
        class=${J(e)}
        ?disabled=${this.disabled}
        part="wrapper"
      >
        <div class="visible-wrapper" part="visible-wrapper">
          ${this.hasLeadingIcon?ce`<span class="leading" part="leading"
                  ><slot name="leading-icon"></slot
                ></span>`:w}
          ${this.type!=="IconOnly"?ce`<span class="label" part="label"><slot></slot></span>`:w}
          ${this.sortable?ce`<span class="trailing sort-icon" part="sort-icon"
                  >${this._renderSortIcon()}</span
                >`:w}
        </div>
        ${this.showDivider?ce`<div class="divider" part="divider"></div>`:w}
      </${t}>
    `}_renderSortIcon(){switch(this.sortDirection){case"asc":return ce`<obi-chevron-up-google></obi-chevron-up-google>`;case"desc":return ce`<obi-chevron-down-google></obi-chevron-down-google>`;default:return w}}};co.styles=Q(Bp);Uo([l({type:String})],co.prototype,"type",2);Uo([l({type:Boolean})],co.prototype,"disabled",2);Uo([l({type:Boolean})],co.prototype,"hasLeadingIcon",2);Uo([l({type:String})],co.prototype,"sortDirection",2);Uo([l({type:Boolean})],co.prototype,"showDivider",2);Uo([l({type:Boolean})],co.prototype,"checked",2);Uo([l({type:Boolean})],co.prototype,"sortable",2);co=Uo([x("obc-table-header-item")],co);var o7=Object.defineProperty;var i7=Object.getOwnPropertyDescriptor;var Ep=(e,t,i,o)=>{var r=o>1?void 0:o?i7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)o7(t,i,r);return r};var Rl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9998 13.0002H4.99976V11.0002H18.9998V13.0002Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9998 13.0002H4.99976V11.0002H18.9998V13.0002Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Rl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Ep([l({type:Boolean})],Rl.prototype,"useCssColor",2);Rl=Ep([x("obi-check-mixed")],Rl);var a7=Object.defineProperty;var n7=Object.getOwnPropertyDescriptor;var Rp=(e,t,i,o)=>{var r=o>1?void 0:o?n7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)a7(t,i,r);return r};var Il=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8.99991 16.17L4.82991 12L3.40991 13.41L8.99991 19L20.9999 7L19.5899 5.59L8.99991 16.17Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8.99991 16.17L4.82991 12L3.40991 13.41L8.99991 19L20.9999 7L19.5899 5.59L8.99991 16.17Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Il.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;Rp([l({type:Boolean})],Il.prototype,"useCssColor",2);Il=Rp([x("obi-check-google")],Il);var Ip=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.visually-hidden {
  box-sizing: border-box;
  display: flex;
  height: var(--ui-components-checkbox-touch-target-size);
  min-width: var(--ui-components-checkbox-touch-target-size);
  min-height: var(--ui-components-checkbox-touch-target-size);
  padding: 0px var(--ui-components-checkbox-margin);
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  user-select: none;
  cursor: pointer;
  outline: none;
}

.visually-hidden.state-loading {
    cursor: progress;
  }

.visually-hidden.disabled {
    cursor: not-allowed;
  }

.checkbox-container {
  display: flex;
  padding: 0px;
  align-items: center;
  justify-content: center;
}

.checkbox-loading-spinner {
  width: var(--global-size-spacing-icon-icon-size-small);
  height: var(--global-size-spacing-icon-icon-size-small);
  align-self: center;
  margin: auto;
  animation: checkbox-loading-spin 1000ms linear infinite;
}

.checkbox-loading-spinner circle {
    fill: none;
    stroke: currentColor;
    stroke-width: var(
      --ui-components-progressbars-progress-bar--circular-bar-weight-small
    );
    stroke-linecap: round;
    stroke-dasharray: 24 14;
  }

.state-loading.status-unchecked .checkbox-loading-spinner {
    color: var(--element-neutral-color);
  }

.state-loading.status-checked .checkbox-loading-spinner {
    color: var(--element-active-inverted-color);
  }

.state-loading.status-mixed .checkbox-loading-spinner {
    color: var(--instrument-enhanced-secondary-color);
  }

.checkbox-container.status-unchecked:not(.disabled):hover .checkbox-box {
  background: var(--indent-hover-background-color);
  border-color: var(--indent-hover-border-color);
}

.checkbox-container.status-unchecked:not(.disabled):active .checkbox-box {
  background: var(--indent-pressed-background-color);
  border-color: var(--indent-pressed-border-color);
}

.checkbox-container.status-unchecked:not(.disabled):focus-visible
  .checkbox-box {
  background: var(--indent-focused-background-color);
  border-color: var(--indent-focused-border-color);
}

.checkbox-container.status-checked:not(.disabled):hover .checkbox-box,
.checkbox-container.status-mixed:not(.disabled):hover .checkbox-box {
  background: var(--selected-hover-background-color);
  border-color: var(--selected-hover-border-color);
}

.checkbox-container.status-checked:not(.disabled):active .checkbox-box,
.checkbox-container.status-mixed:not(.disabled):active .checkbox-box {
  background: var(--selected-pressed-background-color);
  border-color: var(--selected-pressed-border-color);
}

.checkbox-container.status-checked:not(.disabled):focus-visible .checkbox-box,
.checkbox-container.status-mixed:not(.disabled):focus-visible .checkbox-box {
  background: var(--selected-focused-background-color);
  border-color: var(--selected-focused-border-color);
}

.checkbox-icon {
  width: var(--global-size-spacing-icon-icon-size-regular);
  height: var(--global-size-spacing-icon-icon-size-regular);
  flex-shrink: 0;
}

.status-checked .checkbox-icon {
    color: var(--on-selected-active-color);
  }

.status-unchecked:not(.no-hover-effects) {
            cursor: pointer;
}

.status-unchecked:not(.no-hover-effects):focus {
            outline: none;
}

.status-unchecked:not(.no-hover-effects) .checkbox-box {
            border-color: var(--indent-enabled-border-color);
            background-color: var(--indent-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--indent-enabled-border-color);
            --base-background-color: var(--indent-enabled-background-color);
}

.status-unchecked.activated:not(.no-hover-effects) .checkbox-box {
            border-color: var(--indent-activated-border-color);
            background-color: var(--indent-activated-background-color);
            --base-border-color: var(--indent-activated-border-color);
            --base-background-color: var(--indent-activated-background-color);
}

@media (hover:hover) {

.status-unchecked:not(.no-hover-effects):hover .checkbox-box {
                        border-color: color-mix(in srgb, var(--indent-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--indent-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.status-unchecked:not(.no-hover-effects):active .checkbox-box {
            border-color: var(--indent-pressed-border-color);
            background-color: var(--indent-pressed-background-color);
}

.status-unchecked:not(.no-hover-effects):focus-visible .checkbox-box {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.status-unchecked:not(.no-hover-effects):disabled .checkbox-box {
            border-color: var(--indent-disabled-border-color);
            background-color: var(--indent-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-indent-disabled-color) !important;
}

.status-unchecked.disabled:not(.no-hover-effects) .checkbox-box {
            border-color: var(--indent-disabled-border-color);
            background-color: var(--indent-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-indent-disabled-color) !important;
}

.status-unchecked:not(.no-hover-effects):disabled {
            cursor: not-allowed;
}

.status-unchecked.disabled:not(.no-hover-effects) {
            cursor: not-allowed;
}

.status-unchecked:not(.no-hover-effects):not(.disabled) .checkbox-box,.status-unchecked:not(.no-hover-effects):not(.disabled):hover .checkbox-box {
    border-color: var(--element-symbol-color);
  }

.status-unchecked.no-hover-effects .checkbox-box {
            border-color: var(--indent-enabled-border-color);
            background-color: var(--indent-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--indent-enabled-border-color);
            --base-background-color: var(--indent-enabled-background-color);
}

.status-checked.no-hover-effects .checkbox-box {
            border-color: var(--selected-enabled-border-color);
            background-color: var(--selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--selected-enabled-border-color);
            --base-background-color: var(--selected-enabled-background-color);
}

.status-mixed.no-hover-effects .checkbox-box {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

.status-checked:not(.no-hover-effects) {
            cursor: pointer;
}

.status-checked:not(.no-hover-effects):focus {
            outline: none;
}

.status-checked:not(.no-hover-effects) .checkbox-box {
            border-color: var(--selected-enabled-border-color);
            background-color: var(--selected-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--selected-enabled-border-color);
            --base-background-color: var(--selected-enabled-background-color);
}

.status-checked.activated:not(.no-hover-effects) .checkbox-box {
            border-color: var(--selected-activated-border-color);
            background-color: var(--selected-activated-background-color);
            --base-border-color: var(--selected-activated-border-color);
            --base-background-color: var(--selected-activated-background-color);
}

@media (hover:hover) {

.status-checked:not(.no-hover-effects):hover .checkbox-box {
                        border-color: color-mix(in srgb, var(--selected-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--selected-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.status-checked:not(.no-hover-effects):active .checkbox-box {
            border-color: var(--selected-pressed-border-color);
            background-color: var(--selected-pressed-background-color);
}

.status-checked:not(.no-hover-effects):focus-visible .checkbox-box {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.status-checked:not(.no-hover-effects):disabled .checkbox-box {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.status-checked.disabled:not(.no-hover-effects) .checkbox-box {
            border-color: var(--selected-disabled-border-color);
            background-color: var(--selected-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-selected-disabled-color) !important;
}

.status-checked:not(.no-hover-effects):disabled {
            cursor: not-allowed;
}

.status-checked.disabled:not(.no-hover-effects) {
            cursor: not-allowed;
}

.status-mixed:not(.no-hover-effects) {
            cursor: pointer;
}

.status-mixed:not(.no-hover-effects):focus {
            outline: none;
}

.status-mixed:not(.no-hover-effects) .checkbox-box {
            border-color: var(--amplified-enabled-border-color);
            background-color: var(--amplified-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--amplified-enabled-border-color);
            --base-background-color: var(--amplified-enabled-background-color);
}

.status-mixed.activated:not(.no-hover-effects) .checkbox-box {
            border-color: var(--amplified-activated-border-color);
            background-color: var(--amplified-activated-background-color);
            --base-border-color: var(--amplified-activated-border-color);
            --base-background-color: var(--amplified-activated-background-color);
}

@media (hover:hover) {

.status-mixed:not(.no-hover-effects):hover .checkbox-box {
                        border-color: color-mix(in srgb, var(--amplified-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--amplified-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.status-mixed:not(.no-hover-effects):active .checkbox-box {
            border-color: var(--amplified-pressed-border-color);
            background-color: var(--amplified-pressed-background-color);
}

.status-mixed:not(.no-hover-effects):focus-visible .checkbox-box {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.status-mixed:not(.no-hover-effects):disabled .checkbox-box {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.status-mixed.disabled:not(.no-hover-effects) .checkbox-box {
            border-color: var(--amplified-disabled-border-color);
            background-color: var(--amplified-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-amplified-disabled-color) !important;
}

.status-mixed:not(.no-hover-effects):disabled {
            cursor: not-allowed;
}

.status-mixed.disabled:not(.no-hover-effects) {
            cursor: not-allowed;
}

.checkbox-box {
  box-sizing: border-box;
  position: relative;
  display: flex;
  width: var(--ui-components-checkbox-visual-target-size);
  height: var(--ui-components-checkbox-visual-target-size);
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-radius: var(--ui-components-checkbox-border-radius);
  border: 1px solid transparent;
  background: transparent;
}

.status-mixed:not(.disabled) .checkbox-box,.status-mixed:not(.disabled):hover .checkbox-box,.status-mixed:not(.disabled):active .checkbox-box {
    border-color: var(--instrument-enhanced-secondary-color);
  }

:is(.status-unchecked.no-hover-effects .checkbox-box) {
            border-color: var(--indent-enabled-border-color);
            background-color: var(--indent-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--indent-enabled-border-color);
            --base-background-color: var(--indent-enabled-background-color);
}

.status-unchecked.no-hover-effects .checkbox-box {
    border-color: var(--element-symbol-color);
  }

.status-unchecked.state-enabled:not(.disabled):not(
    .no-hover-effects
  ):focus-visible
  .checkbox-box {
  border-color: transparent;
}

@keyframes checkbox-loading-spin {
  to {
    transform: rotate(360deg);
  }
}
`;var l7=Object.defineProperty;var s7=Object.getOwnPropertyDescriptor;var ua=(e,t,i,o)=>{var r=o>1?void 0:o?s7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)l7(t,i,r);return r};var po=(e=>{e["unchecked"]="unchecked";e["checked"]="checked";e["mixed"]="mixed";return e})(po||{});var Wo=class extends k{constructor(){super(...arguments);this.status="unchecked";this.state="enabled";this.disabled=false;this.hasHoverEffects=true}get _isInteractionLocked(){return this.disabled||this.state==="loading"}updated(e){if(e.has("disabled")){this.dispatchEvent(new CustomEvent("disabled",{detail:{status:this.status,disabled:this.disabled}}))}}toggleStatus(){if(this._isInteractionLocked)return;if(this.status==="checked"){this.status="unchecked"}else{this.status="checked"}this.dispatchEvent(new CustomEvent("change",{detail:{status:this.status,disabled:this.disabled}}))}handleKeydown(e){if(e.key===" "||e.key==="Space"||e.key==="Enter"){e.preventDefault();this.toggleStatus()}}get _computedAriaChecked(){switch(this.status){case"checked":return"true";case"mixed":return"mixed";case"unchecked":default:return"false"}}focus(e){this.checkboxControl?.focus(e)}syncFocusVisibleAttribute(){const e=this.checkboxControl?.matches(":focus-visible");this.toggleAttribute("data-focus-visible",Boolean(e))}handleControlFocus(){queueMicrotask(()=>this.syncFocusVisibleAttribute())}handleControlBlur(){this.removeAttribute("data-focus-visible")}render(){const e=this.getAttribute("aria-label")??void 0;const t=this.getAttribute("aria-labelledby")??void 0;const i=this.getAttribute("aria-describedby")??void 0;const o=t?void 0:e??"Checkbox item";return h`
      <div
        class=${J({"visually-hidden":true,[`status-${this.status}`]:true,[`state-${this.state}`]:true,disabled:this.disabled,"no-hover-effects":!this.hasHoverEffects})}
        role="checkbox"
        aria-checked=${this._computedAriaChecked}
        aria-label=${$e(o)}
        aria-labelledby=${$e(t)}
        aria-describedby=${$e(i)}
        aria-disabled=${this._isInteractionLocked?"true":"false"}
        aria-busy=${this.state==="loading"?"true":"false"}
        tabindex=${this._isInteractionLocked?"-1":"0"}
        @click=${this.toggleStatus}
        @keydown=${this.handleKeydown}
        @focus=${this.handleControlFocus}
        @blur=${this.handleControlBlur}
      >
        <div class="checkbox-container">
          <div class="checkbox-box">
            ${this.state==="loading"?h`
                  <svg
                    class="checkbox-loading-spinner type-indeterminate size-small style-regular"
                    viewBox="0 0 16 16"
                    aria-hidden="true"
                  >
                    <circle cx="8" cy="8" r="6"></circle>
                  </svg>
                `:this.status==="checked"?h`<obi-check-google
                    class="checkbox-icon"
                  ></obi-check-google>`:this.status==="mixed"?h`<obi-check-mixed
                      class="checkbox-icon"
                    ></obi-check-mixed>`:h`<span class="checkbox-icon"></span>`}
          </div>
        </div>
      </div>
    `}};Wo.styles=[Q(Ip)];ua([l({type:String})],Wo.prototype,"status",2);ua([l({type:String})],Wo.prototype,"state",2);ua([l({type:Boolean})],Wo.prototype,"disabled",2);ua([l({type:Boolean,attribute:false})],Wo.prototype,"hasHoverEffects",2);ua([Do(".visually-hidden")],Wo.prototype,"checkboxControl",2);Wo=ua([x("obc-checkbox")],Wo);var Np=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: inline-block;
}

.wrapper {
  --obc-tag-padding-block: 1px;
  --obc-tag-border-width: 1px;
  display: inline-flex;
  min-height: var(--ui-components-tag-visual-target, 24px);
  padding: var(
    --ui-components-tag-padding,
    var(--obc-tag-padding-block)
      var(--ui-components-tag-padding-horizontal, 6px)
  );
  align-items: center;
  flex-shrink: 0;
  border-radius: var(--ui-components-tag-border-radius, 4px);
  border: 1px solid var(--indent-enabled-border-color);
  background: var(--indent-enabled-background-color);
}

.tag-label-container {
  display: flex;
  padding: 0 var(--ui-components-tag-label-spacing, 4px);
  justify-content: center;
  align-items: center;
}

.tag-label {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  line-height: var(--ui-components-tag-label-line-height, 12px);
  white-space: normal;
  word-break: normal;
  overflow-wrap: normal;
}

.tag-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--ui-components-tag-icon-size, 16px);
  height: var(--ui-components-tag-icon-size, 16px);
  max-width: calc(
    var(--ui-components-tag-visual-target, 24px) -
      (var(--obc-tag-padding-block) + var(--obc-tag-padding-block)) -
      (var(--obc-tag-border-width) + var(--obc-tag-border-width))
  );
  max-height: calc(
    var(--ui-components-tag-visual-target, 24px) -
      (var(--obc-tag-padding-block) + var(--obc-tag-padding-block)) -
      (var(--obc-tag-border-width) + var(--obc-tag-border-width))
  );
  flex-shrink: 0;
  line-height: 0;
}

.tag-icon-wrapper ::slotted(*) {
  display: block;
  width: 100%;
  height: 100%;
}

/* Color variants */

.color-gray {
  background: var(--indent-enabled-background-color);
  border-color: var(--indent-enabled-border-color);
  color: var(--on-indent-active-color);
}

.color-gray .tag-icon-wrapper {
    color: var(--on-indent-neutral-color);
  }

.color-blue {
  border-color: var(--base-blue-100);
  background-color: var(--base-blue-050);
  color: var(--base-blue-600);
}

.color-blue .tag-icon-wrapper {
    color: var(--base-blue-500);
  }

.color-cyan {
  border-color: var(--base-cyan-100);
  background-color: var(--base-cyan-050);
  color: var(--base-cyan-600);
}

.color-cyan .tag-icon-wrapper {
    color: var(--base-cyan-500);
  }

.color-teal {
  border-color: var(--base-teal-100);
  background-color: var(--base-teal-050);
  color: var(--base-teal-600);
}

.color-teal .tag-icon-wrapper {
    color: var(--base-teal-500);
  }

.color-green {
  border-color: var(--base-mint-100, #bfe5d5);
  background-color: var(--base-mint-050, #e2f3eb);
  color: var(--base-mint-600, #00452f);
}

.color-green .tag-icon-wrapper {
    color: var(--base-mint-500, #005f43);
  }

.color-yellow {
  border-color: var(--base-yellow-100);
  background-color: var(--base-yellow-050);
  color: var(--base-yellow-600);
}

.color-yellow .tag-icon-wrapper {
    color: var(--base-yellow-500);
  }

.color-orange {
  border-color: var(--base-orange-100);
  background-color: var(--base-orange-050);
  color: var(--base-orange-600);
}

.color-orange .tag-icon-wrapper {
    color: var(--base-orange-500);
  }

.color-red {
  border-color: var(--base-red-100);
  background-color: var(--base-red-050);
  color: var(--base-red-600);
}

.color-red .tag-icon-wrapper {
    color: var(--base-red-500);
  }

.color-purple {
  border-color: var(--base-purple-100);
  background-color: var(--base-purple-050);
  color: var(--base-purple-600);
}

.color-purple .tag-icon-wrapper {
    color: var(--base-purple-500);
  }

.color-indigo {
  border-color: var(--base-indigo-100);
  background-color: var(--base-indigo-050);
  color: var(--base-indigo-600);
}

.color-indigo .tag-icon-wrapper {
    color: var(--base-indigo-500);
  }
`;var c7=Object.defineProperty;var d7=Object.getOwnPropertyDescriptor;var Nl=(e,t,i,o)=>{var r=o>1?void 0:o?d7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)c7(t,i,r);return r};var M1=(e=>{e["gray"]="gray";e["blue"]="blue";e["cyan"]="cyan";e["teal"]="teal";e["green"]="green";e["yellow"]="yellow";e["orange"]="orange";e["red"]="red";e["purple"]="purple";e["indigo"]="indigo";return e})(M1||{});var fa=class extends k{constructor(){super(...arguments);this.label="Label";this.color="gray";this.hasIcon=false}renderLeadingIcon(){if(this.hasIcon){return h`
        <div class="tag-icon-wrapper">
          <slot></slot>
        </div>
      `}return h``}render(){return h`
      <div
        class=${J({wrapper:true,["color-"+this.color]:true})}
      >
        ${this.renderLeadingIcon()}
        <div class="tag-label-container">
          <span class="tag-label">${this.label}</span>
        </div>
      </div>
    `}};fa.styles=Q(Np);Nl([l({type:String})],fa.prototype,"label",2);Nl([l({type:String})],fa.prototype,"color",2);Nl([l({type:Boolean})],fa.prototype,"hasIcon",2);fa=Nl([x("obc-tag")],fa);var H1={CANVAS_PADDING:32,CHART_WIDTH:256,MIN_CHART_WIDTH:48,MIN_HEIGHT_WITH_LABELS:192};function jp(e,t=1){return e-t}function Fp(e,t,i,o,r=1){const a=jp(o,r);const n=i-t;const p=(-e+t)*a/n+a/2;return p+r/2}function Up(e,t,i,o,r=1){const a=jp(o,r);const n=i-t;const p=(e-t)*a/n;return p+r/2}function an(e,t,i,o,r=1){const a=r/2;let n=e;let p=t;if(e===i){n=e+a;p=t-a}if(e+t===o){p=p-a}return{x:n,width:p}}function nn(e,t,i,o,r=1){const a=r/2;let n=e;let p=t;if(e===i){n=e+a;p=t-a}if(e+t===o){p=p-a}return{y:n,height:p}}var Mi=(e=>{e["vertical"]="vertical";e["horizontal"]="horizontal";return e})(Mi||{});var ln=(e=>{e["left"]="left";e["right"]="right";e["top"]="top";e["bottom"]="bottom";return e})(ln||{});var Hi=(e=>{e["regular"]="regular";e["condensed"]="condensed";return e})(Hi||{});var sn=(e=>{e["fill"]="fill";e["tint"]="tint";return e})(sn||{});var A1=(e=>{e["center"]="center";e["inner"]="inner";e["outer"]="outer";return e})(A1||{});var p7="--instrument-components-watchface-frame-regular-border-radius";function h7(e,t){if(!e)return void 0;const i=e.trim();const o=Number.parseFloat(i);if(!Number.isFinite(o))return void 0;if(i.endsWith("px"))return o;const r=typeof getComputedStyle==="function";if(i.endsWith("rem")){if(!r)return void 0;const a=t?.documentElement??(typeof document!=="undefined"?document.documentElement:void 0);if(!a)return void 0;const n=Number.parseFloat(getComputedStyle(a).fontSize);return Number.isFinite(n)?o*n:void 0}if(i.endsWith("em")){if(!r)return void 0;const a=t?.element;if(!a)return void 0;const n=Number.parseFloat(getComputedStyle(a).fontSize);return Number.isFinite(n)?o*n:void 0}return o}function Yp(e,t,i=p7){const o=t==="condensed"?4:8;if(typeof getComputedStyle!=="function")return o;const r=getComputedStyle(e).getPropertyValue(i).trim();const a=h7(r,{element:e,documentElement:e.ownerDocument?.documentElement??(typeof document!=="undefined"?document.documentElement:void 0)});return a??o}function Qp(e,t){if(typeof MutationObserver==="undefined")return void 0;const i=new MutationObserver(()=>t());const o=[e];let r=e.parentElement;while(r){o.push(r);r=r.parentElement}const a=e.ownerDocument?.documentElement;if(a)o.push(a);for(const n of o){i.observe(n,{attributes:true,attributeFilter:["class","style"]})}return i}function u7(e){return e==="condensed"?4:8}function f7(e){const t=u7(e.scaleType);const i=e.borderRadius;return typeof i==="number"&&Number.isFinite(i)&&i>=0?i:t}function Fl(e){const t=Number.isFinite(e.barThickness)?e.barThickness:0;if(!e.hasBar)return t;const i=f7(e);return Math.max(t,i*2)}function cn(e){const t=Number.isFinite(e.tickThickness)?e.tickThickness:0;if(e.scaleType==="condensed"){const i=14;return Math.min(t,i)}return t}function Kp(e){return{orientation:e.orientation,side:e.side,hasBar:e.hasBar,hasScale:e.hasScale,labels:e.labels,barThickness:Fl(e),tickThickness:cn(e),labelThickness:e.labelThickness,length:e.length,scaleType:e.scaleType}}function Z1(e,t){if(e.orientation==="vertical"){return{x:t.viewBoxPerpStart,y:-e.length/2,width:t.viewBoxThickness,height:e.length}}return{x:0,y:t.viewBoxPerpStart,width:e.length,height:t.viewBoxThickness}}function Ul(e){const{containerMainAxisSize:t,scaleReferenceSize:i}=e;if(t<=0||i<=0){return 1}return t/i}function T1(e){const t=e.hasBar?e.barThickness:0;const i=cn(e);const o=e.hasScale?i:0;const r=e.labels?e.labelThickness:0;const a=t+o+r;const n=e.orientation==="vertical"&&e.side==="right"||e.orientation==="horizontal"&&e.side==="bottom";const p=n?0:-a;return{thickness:a,viewBoxPerpStart:p,viewBoxLength:e.length,viewBoxThickness:a}}function xt(e){return e.orientation==="vertical"}function Re(e){return e.orientation==="vertical"&&e.side==="right"||e.orientation==="horizontal"&&e.side==="bottom"}function P1(e,t){return e<=0&&t>=0}function v7(e){const t=e.touching??false;return aa({value:e.value,setpoint:e.setpoint,touching:t,auto:e.autoAtSetpoint,deadband:e.autoAtSetpointDeadband,atSetpointManual:e.atSetpoint})}function m7(e){const t=e.touching??false;if(t&&e.newSetpoint===void 0){return at.focus}const i=v7(e);if(i){const o=e.setpoint!==void 0&&Math.abs(e.setpoint)<e.setpointAtZeroDeadband;if(o){return at.equalZero}return at.equal}return at.notEqual}function Wp(e){return e.priority===me.enhanced?gi.enhanced:gi.regular}function g7(e){if(e.setpointDisabled!==void 0){return e.setpointDisabled}if(e.setpointOverride){return false}if(e.state===Le.loading||e.state===Le.off){return true}return false}function Xp(e){const t=e.priority===me.enhanced;let i=e.fillMode==="tint"?t?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)":t?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";let o=t?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";let r=t?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)";let a=t?"var(--instrument-enhanced-primary-color)":"var(--instrument-regular-primary-color)";if(e.state===Le.loading||e.state===Le.off){i="transparent";o="var(--instrument-frame-tertiary-color)";r="var(--instrument-frame-tertiary-color)";a="var(--instrument-frame-tertiary-color)"}return{barFillColor:i,markerFillColor:o,markerStrokeColor:r,setpointColor:a}}function b7(e,t){return e.map(i=>{const o=t!==void 0&&t>=i.min&&t<=i.max;const r=o?de.triggered:i.hinted?de.hinted:de.regular;return{min:i.min,max:i.max,type:i.type,state:r}})}function Go(e){if(xt(e)){return(e.paddingStart-e.paddingEnd)/2}return e.paddingStart}function Wl(e){return Math.max(0,e.length-e.paddingStart-e.paddingEnd)}function pt(e,t){const i=Wl(e);if(xt(e)){return Fp(t,e.minValue,e.maxValue,i)+Go(e)}return Up(t,e.minValue,e.maxValue,i)+Go(e)}function Jp(e){const t=e==="condensed";return{primary:t?10:20,secondary:t?4:8,tertiary:t?2:4,main:t?10:20}}function dn(e){return e.hasBar?Re(e)?e.barThickness:-e.barThickness:0}function Gl(){return 4}function Gp(){return 8}function V1(e,t,i,o){const r="var(--instrument-frame-tertiary-color)";const a=1;if(xt(e)){const f=i;const g=i+o;const m=t;return c`<line x1=${f} x2=${g} y1=${m} y2=${m} stroke=${r} stroke-width=${a} vector-effect="non-scaling-stroke"/>`}const n=i;const p=i+o;const d=t;return c`<line x1=${d} x2=${d} y1=${n} y2=${p} stroke=${r} stroke-width=${a} vector-effect="non-scaling-stroke"/>`}function S1(e,t,i,o,r){const a=[];const n=[];if(t<=0||!Number.isFinite(t))return{svgs:a,values:n};const p=P1(e.minValue,e.maxValue);const d=f=>{if(r.includes(f))return;n.push(f);a.push(V1(e,pt(e,f),i,o))};if(p){for(let f=t;f<=e.maxValue;f+=t)d(f);for(let f=-t;f>=e.minValue;f-=t)d(f)}else{const f=Math.ceil(e.minValue/t)*t;for(let g=f;g<=e.maxValue;g+=t)d(g)}return{svgs:a,values:n}}function y7(e){if(!e.hasScale)return[];const t=[];const i=[];const o=dn(e);const r=Gl();const a=Re(e)?o+r:o-r;const{primary:n,secondary:p,tertiary:d,main:f}=Jp(e.scaleType);if(P1(e.minValue,e.maxValue)){const g=0===e.minValue||0===e.maxValue;const m=e.scaleBackground&&g;if(!m){const u=n;const M=a;t.push(V1(e,pt(e,0),M,Re(e)?u:-u))}i.push(0)}if(e.mainTickmarks){const g=e.frameStyle==="flat"?o:a;const m=e.frameStyle==="flat"?f+4:f;const u=Re(e)?m:-m;const M=e.mainTickmarks.length>0?e.mainTickmarks:[e.minValue,0,e.maxValue];for(const C of M){if(C<e.minValue||C>e.maxValue)continue;if(e.scaleBackground&&(C===e.minValue||C===e.maxValue)){i.push(C);continue}t.push(V1(e,pt(e,C),g,u));i.push(C)}}if(e.primaryTickmarkInterval!==void 0&&e.primaryTickmarkInterval>0){const{svgs:g,values:m}=S1(e,e.primaryTickmarkInterval,a,Re(e)?n:-n,i);t.push(...g);i.push(...m)}if(e.secondaryTickmarkInterval!==void 0&&e.secondaryTickmarkInterval>0){const{svgs:g}=S1(e,e.secondaryTickmarkInterval,a,Re(e)?p:-p,i);t.push(...g)}if(e.tertiaryTickmarkInterval!==void 0&&e.tertiaryTickmarkInterval>0){const{svgs:g}=S1(e,e.tertiaryTickmarkInterval,a,Re(e)?d:-d,i);t.push(...g)}return t}function w7(e){if(!e.labels||e.primaryTickmarkInterval===void 0)return[];const t=e.primaryTickmarkInterval;if(t<=0||!Number.isFinite(t))return[];const i="var(--font-family-main)";const o="var(--instrument-tick-mark-label-secondary-color)";const r="calc(var(--global-typography-ui-label-font-size) / var(--scale, 1))";const a=dn(e);const n=cn(e);const p=Re(e)?a+(e.hasScale?n:0)+Gp():a-(e.hasScale?n:0)-Gp();const d=P1(e.minValue,e.maxValue);const f=[];const g=m=>{const u=pt(e,m);if(xt(e)){const H=p;const _=u;const S=Re(e)?"start":"end";f.push(c`<text x=${H} y=${_} text-anchor=${S} dominant-baseline="middle" font-family=${i} style="font-size: ${r}" fill=${o}>${m}</text>`);return}const M=p;const C=u;const A=Re(e)?"hanging":"auto";f.push(c`<text x=${C} y=${M} text-anchor="middle" dominant-baseline=${A} font-family=${i} style="font-size: ${r}" fill=${o}>${m}</text>`)};if(d){for(let m=0;m<=e.maxValue;m+=t)g(m);for(let m=-t;m>=e.minValue;m-=t)g(m)}else{const m=Math.ceil(e.minValue/t)*t;for(let u=m;u<=e.maxValue;u+=t)g(u)}return f}function C7(e){if(!e.hasBar)return w;const t=e.scaleType==="condensed"?4:8;const i=e.borderRadius??t;const o=1;let r;if(e.barContainerStyle!==void 0){r=e.barContainerStyle==="secondary"?"var(--instrument-frame-secondary-color)":"var(--instrument-frame-primary-color)"}else{r=e.scaleBackground?"var(--instrument-frame-secondary-color)":"var(--instrument-frame-primary-color)"}const a="var(--instrument-frame-tertiary-color)";const n=Wl(e);const p=Go(e);let d=true;let f=true;let g=true;let m=true;if(e.borderRadiusPosition){if(e.borderRadiusPosition===Or.middleChild||e.borderRadiusPosition===Or.middleRoundedChild){d=false;f=false;g=false;m=false}else if(xt(e)){const T=e.side==="right";const Z=e.borderRadiusPosition===Or.innerFirstChild;if(T){d=Z;g=Z;f=!Z;m=!Z}else{d=!Z;g=!Z;f=Z;m=Z}}else{const T=e.side==="bottom";const Z=e.borderRadiusPosition===Or.innerFirstChild;if(T){d=Z;f=Z;g=!Z;m=!Z}else{d=!Z;f=!Z;g=Z;m=Z}}}const u=i;const M=d&&f&&g&&m;const C=!d&&!f&&!g&&!m;if(xt(e)){let T=Re(e)?0:-e.barThickness;let Z=-n/2+p;let q=e.barThickness;let j=n;const P=e.side==="right";let be;let he;if(e.scaleBackground){if(P){be=0;he=e.barThickness+1}else{be=-e.barThickness-1;he=0}}else{be=P?0:-e.barThickness;he=P?e.barThickness:0}const se=an(T,q,be,he,o);T=se.x;q=se.width;const ke=nn(Z,j,-n/2+p,n/2+p,o);Z=ke.y;j=ke.height;if(M||C){const ie=M?u:0;const ue=M?u:0;if(e.scaleBackground){const Ee=e.side==="right";let ne;if(Ee){ne=`M ${T} ${Z+(C?0:u)} L ${T} ${Z+j-(C?0:u)}`;if(!C)ne+=` Q ${T} ${Z+j} ${T+u} ${Z+j}`;ne+=` L ${T+q-(C?0:u)} ${Z+j}`;if(!C)ne+=` Q ${T+q} ${Z+j} ${T+q} ${Z+j-u}`;ne+=` M ${T+q} ${Z+(C?0:u)}`;if(!C)ne+=` Q ${T+q} ${Z} ${T+q-u} ${Z}`;ne+=` L ${T+(C?0:u)} ${Z}`;if(!C)ne+=` Q ${T} ${Z} ${T} ${Z+u}`}else{ne=`M ${T+(C?0:u)} ${Z}`;ne+=` L ${T+q-(C?0:u)} ${Z}`;if(!C)ne+=` Q ${T+q} ${Z} ${T+q} ${Z+u}`;ne+=` L ${T+q} ${Z+j-(C?0:u)}`;if(!C)ne+=` Q ${T+q} ${Z+j} ${T+q-u} ${Z+j}`;ne+=` L ${T+(C?0:u)} ${Z+j}`;if(!C)ne+=` Q ${T} ${Z+j} ${T} ${Z+j-u}`;ne+=` M ${T} ${Z+(C?0:u)}`;if(!C)ne+=` Q ${T} ${Z} ${T+u} ${Z}`}return c`
          <rect x=${T} y=${Z} width=${q} height=${j} rx=${ie} ry=${ue} fill=${r} stroke="none"/>
          <path d="${ne}" fill="none" stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
        `}return c`<rect x=${T} y=${Z} width=${q} height=${j} rx=${ie} ry=${ue} fill=${r} stroke=${a} vector-effect="non-scaling-stroke"/>`}const W=T;const N=Z;const ye=q;const we=j;let oe=`M ${W+(d?u:0)} ${N}`;oe+=` L ${W+ye-(f?u:0)} ${N}`;if(f){oe+=` Q ${W+ye} ${N} ${W+ye} ${N+u}`}oe+=` L ${W+ye} ${N+we-(m?u:0)}`;if(m){oe+=` Q ${W+ye} ${N+we} ${W+ye-u} ${N+we}`}oe+=` L ${W+(g?u:0)} ${N+we}`;if(g){oe+=` Q ${W} ${N+we} ${W} ${N+we-u}`}oe+=` L ${W} ${N+(d?u:0)}`;if(d){oe+=` Q ${W} ${N} ${W+u} ${N}`}oe+=` Z`;if(e.scaleBackground){const ie=e.side==="right";let ue;if(ie){ue=`M ${W} ${N+(d?u:0)}`;if(d)ue+=` Q ${W} ${N} ${W+u} ${N}`;ue+=` L ${W+ye-(f?u:0)} ${N}`;if(f)ue+=` Q ${W+ye} ${N} ${W+ye} ${N+u}`;ue+=` M ${W+ye} ${N+we-(m?u:0)}`;if(m)ue+=` Q ${W+ye} ${N+we} ${W+ye-u} ${N+we}`;ue+=` L ${W+(g?u:0)} ${N+we}`;if(g)ue+=` Q ${W} ${N+we} ${W} ${N+we-u}`;ue+=` L ${W} ${N+(d?u:0)}`}else{ue=`M ${W+(d?u:0)} ${N}`;ue+=` L ${W+ye-(f?u:0)} ${N}`;if(f)ue+=` Q ${W+ye} ${N} ${W+ye} ${N+u}`;ue+=` L ${W+ye} ${N+we-(m?u:0)}`;if(m)ue+=` Q ${W+ye} ${N+we} ${W+ye-u} ${N+we}`;ue+=` L ${W+(g?u:0)} ${N+we}`;if(g)ue+=` Q ${W} ${N+we} ${W} ${N+we-u}`;ue+=` M ${W} ${N+(d?u:0)}`;if(d)ue+=` Q ${W} ${N} ${W+u} ${N}`}return c`
        <path d=${oe} fill=${r} stroke="none"/>
        <path d="${ue}" fill="none" stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
      `}return c`<path d=${oe} fill=${r} stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>`}let A=Go(e);let H=Re(e)?0:-e.barThickness;let _=n;let S=e.barThickness;const E=e.side==="bottom";let D;let K;if(e.scaleBackground){if(E){D=0;K=e.barThickness+1}else{D=-e.barThickness-1;K=0}}else{D=E?0:-e.barThickness;K=E?e.barThickness:0}const I=an(A,_,A,A+_,o);A=I.x;_=I.width;const Y=nn(H,S,D,K,o);H=Y.y;S=Y.height;if(M||C){const T=M?u:0;const Z=M?u:0;if(e.scaleBackground){const q=e.side==="bottom";let j;if(q){j=`M ${A+(C?0:u)} ${H}`;j+=` L ${A+_-(C?0:u)} ${H}`;if(!C)j+=` Q ${A+_} ${H} ${A+_} ${H+u}`;j+=` L ${A+_} ${H+S-(C?0:u)}`;if(!C)j+=` Q ${A+_} ${H+S} ${A+_-u} ${H+S}`;j+=` M ${A+(C?0:u)} ${H+S}`;if(!C)j+=` Q ${A} ${H+S} ${A} ${H+S-u}`;j+=` L ${A} ${H+(C?0:u)}`;if(!C)j+=` Q ${A} ${H} ${A+u} ${H}`}else{j=`M ${A} ${H+(C?0:u)}`;j+=` L ${A} ${H+S-(C?0:u)}`;if(!C)j+=` Q ${A} ${H+S} ${A+u} ${H+S}`;j+=` L ${A+_-(C?0:u)} ${H+S}`;if(!C)j+=` Q ${A+_} ${H+S} ${A+_} ${H+S-u}`;j+=` L ${A+_} ${H+(C?0:u)}`;if(!C)j+=` Q ${A+_} ${H} ${A+_-u} ${H}`;j+=` M ${A+(C?0:u)} ${H}`;if(!C)j+=` Q ${A} ${H} ${A} ${H+u}`}return c`
        <rect x=${A} y=${H} width=${_} height=${S} rx=${T} ry=${Z} fill=${r} stroke="none"/>
        <path d="${j}" fill="none" stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
      `}return c`<rect x=${A} y=${H} width=${_} height=${S} rx=${T} ry=${Z} fill=${r} stroke=${a} vector-effect="non-scaling-stroke"/>`}const R=A;const B=H;const F=_;const z=S;let ee=`M ${R+(d?u:0)} ${B}`;ee+=` L ${R+F-(f?u:0)} ${B}`;if(f){ee+=` Q ${R+F} ${B} ${R+F} ${B+u}`}ee+=` L ${R+F} ${B+z-(m?u:0)}`;if(m){ee+=` Q ${R+F} ${B+z} ${R+F-u} ${B+z}`}ee+=` L ${R+(g?u:0)} ${B+z}`;if(g){ee+=` Q ${R} ${B+z} ${R} ${B+z-u}`}ee+=` L ${R} ${B+(d?u:0)}`;if(d){ee+=` Q ${R} ${B} ${R+u} ${B}`}ee+=` Z`;if(e.scaleBackground){const T=e.side==="bottom";let Z;if(T){Z=`M ${R+(d?u:0)} ${B}`;Z+=` L ${R+F-(f?u:0)} ${B}`;if(f)Z+=` Q ${R+F} ${B} ${R+F} ${B+u}`;Z+=` L ${R+F} ${B+z-(m?u:0)}`;if(m)Z+=` Q ${R+F} ${B+z} ${R+F-u} ${B+z}`;Z+=` M ${R+(g?u:0)} ${B+z}`;if(g)Z+=` Q ${R} ${B+z} ${R} ${B+z-u}`;Z+=` L ${R} ${B+(d?u:0)}`;if(d)Z+=` Q ${R} ${B} ${R+u} ${B}`}else{Z=`M ${R} ${B+(d?u:0)}`;if(d)Z+=` Q ${R} ${B} ${R+u} ${B}`;Z+=` M ${R+F-(f?u:0)} ${B}`;if(f)Z+=` Q ${R+F} ${B} ${R+F} ${B+u}`;Z+=` L ${R+F} ${B+z-(m?u:0)}`;if(m)Z+=` Q ${R+F} ${B+z} ${R+F-u} ${B+z}`;Z+=` L ${R+(g?u:0)} ${B+z}`;if(g)Z+=` Q ${R} ${B+z} ${R} ${B+z-u}`;Z+=` L ${R} ${B+(d?u:0)}`}return c`
      <path d=${ee} fill=${r} stroke="none"/>
      <path d="${Z}" fill="none" stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
    `}return c`<path d=${ee} fill=${r} stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>`}function k7(e){if(!e.hasBar||e.value===void 0)return w;const t=`obc-bar-fill-clip-${Math.random().toString(36).slice(2)}`;const i=e.scaleType==="condensed"?4:8;const o=e.borderRadius??i;const r=o;const a=Xp(e);const n=e.fillMin??0;const p=e.fillMax??e.value;const d=Math.max(Math.min(n,e.maxValue),e.minValue);const f=Math.max(Math.min(p,e.maxValue),e.minValue);const g=pt(e,d);const m=pt(e,f);const u=8;const M=4;const C=Wl(e);const A=Go(e);let H=true;let _=true;let S=true;let E=true;if(e.borderRadiusPosition){if(e.borderRadiusPosition===Or.middleChild||e.borderRadiusPosition===Or.middleRoundedChild){H=false;_=false;S=false;E=false}else if(xt(e)){const j=e.side==="right";const P=e.borderRadiusPosition===Or.innerFirstChild;if(j){H=P;S=P;_=!P;E=!P}else{H=!P;S=!P;_=P;E=P}}else{const j=e.side==="bottom";const P=e.borderRadiusPosition===Or.innerFirstChild;if(j){H=P;_=P;S=!P;E=!P}else{H=!P;_=!P;S=P;E=P}}}const D=H&&_&&S&&E;const K=!H&&!_&&!S&&!E;if(xt(e)){const j=Re(e)?0:-e.barThickness;const P=e.barThickness;const be=Math.min(g,m);const he=Math.abs(m-g);const se=Re(e)?0:-e.barThickness;const ke=-C/2+A;const W=e.barThickness;const N=C;const ye=K?c`<rect x=${se} y=${ke} width=${W} height=${N} rx=${0} ry=${0}/>`:D?c`<rect x=${se} y=${ke} width=${W} height=${N} rx=${r} ry=${r}/>`:c`<path d=${(()=>{const oe=se;const ie=ke;const ue=W;const Ee=N;let ne=`M ${oe+(H?r:0)} ${ie}`;ne+=` L ${oe+ue-(_?r:0)} ${ie}`;if(_){ne+=` Q ${oe+ue} ${ie} ${oe+ue} ${ie+r}`}ne+=` L ${oe+ue} ${ie+Ee-(E?r:0)}`;if(E){ne+=` Q ${oe+ue} ${ie+Ee} ${oe+ue-r} ${ie+Ee}`}ne+=` L ${oe+(S?r:0)} ${ie+Ee}`;if(S){ne+=` Q ${oe} ${ie+Ee} ${oe} ${ie+Ee-r}`}ne+=` L ${oe} ${ie+(H?r:0)}`;if(H){ne+=` Q ${oe} ${ie} ${oe+r} ${ie}`}ne+=` Z`;return ne})()}/>`;const we=c`<rect x=${j} y=${be} width=${P} height=${he} fill=${a.barFillColor} stroke="none"/>`;if(e.fillMode==="tint"){const oe=pt(e,e.value)-u/2;const ie=c`<rect x=${j} y=${oe} width=${P} height=${u} rx=${M} fill=${a.markerFillColor} stroke=${a.markerStrokeColor} vector-effect="non-scaling-stroke"/>`;return c`<defs>
        <clipPath id=${t} clipPathUnits="userSpaceOnUse">${ye}</clipPath>
      </defs>
      <g clip-path=${`url(#${t})`}>
        ${we}
        ${ie}
      </g>`}return c`<defs>
      <clipPath id=${t} clipPathUnits="userSpaceOnUse">${ye}</clipPath>
    </defs>
    <g clip-path=${`url(#${t})`}>
      ${we}
    </g>`}const I=Re(e)?0:-e.barThickness;const Y=e.barThickness;const R=Math.min(g,m);const B=Math.abs(m-g);const F=Go(e);const z=Re(e)?0:-e.barThickness;const ee=C;const T=e.barThickness;const Z=K?c`<rect x=${F} y=${z} width=${ee} height=${T} rx=${0} ry=${0}/>`:D?c`<rect x=${F} y=${z} width=${ee} height=${T} rx=${r} ry=${r}/>`:c`<path d=${(()=>{const j=F;const P=z;const be=ee;const he=T;let se=`M ${j+(H?r:0)} ${P}`;se+=` L ${j+be-(_?r:0)} ${P}`;if(_){se+=` Q ${j+be} ${P} ${j+be} ${P+r}`}se+=` L ${j+be} ${P+he-(E?r:0)}`;if(E){se+=` Q ${j+be} ${P+he} ${j+be-r} ${P+he}`}se+=` L ${j+(S?r:0)} ${P+he}`;if(S){se+=` Q ${j} ${P+he} ${j} ${P+he-r}`}se+=` L ${j} ${P+(H?r:0)}`;if(H){se+=` Q ${j} ${P} ${j+r} ${P}`}se+=` Z`;return se})()}/>`;const q=c`<rect x=${R} y=${I} width=${B} height=${Y} fill=${a.barFillColor} stroke="none"/>`;if(e.fillMode==="tint"){const j=pt(e,e.value)-u/2;const P=c`<rect x=${j} y=${I} width=${u} height=${Y} rx=${M} fill=${a.markerFillColor} stroke=${a.markerStrokeColor} vector-effect="non-scaling-stroke"/>`;return c`<defs>
      <clipPath id=${t} clipPathUnits="userSpaceOnUse">${Z}</clipPath>
    </defs>
    <g clip-path=${`url(#${t})`}>
      ${q}
      ${P}
    </g>`}return c`<defs>
    <clipPath id=${t} clipPathUnits="userSpaceOnUse">${Z}</clipPath>
  </defs>
  <g clip-path=${`url(#${t})`}>
    ${q}
  </g>`}function L7(e){if(!e.scaleBackground)return w;const t=e.scaleType==="condensed"?4:8;const i=e.borderRadius??t;const o=1;const r="var(--instrument-frame-primary-color)";const a="var(--instrument-frame-tertiary-color)";const{main:n}=Jp(e.scaleType);const p=n+Gl();const d=Wl(e);const f=Go(e);const g=e.orientation==="vertical"&&e.side==="left"||e.orientation==="horizontal"&&e.side==="top";const m=e.orientation==="vertical"&&e.side==="right"||e.orientation==="horizontal"&&e.side==="top";const u=e.orientation==="vertical"&&e.side==="left"||e.orientation==="horizontal"&&e.side==="bottom";const M=e.orientation==="vertical"&&e.side==="right"||e.orientation==="horizontal"&&e.side==="bottom";const C=i;if(xt(e)){const j=e.hasBar?Re(e)?e.barThickness:-e.barThickness:0;let P=Re(e)?j:j-p;let be=-d/2+f;let he=p;let se=d;const ke=e.side==="right";let W;let N;if(e.hasBar){if(ke){W=P-1;N=P+he}else{W=P;N=P+he+1}}else{W=P;N=P+he}const ye=an(P,he,W,N,o);P=ye.x;he=ye.width;const we=nn(be,se,-d/2+f,d/2+f,o);be=we.y;se=we.height;const oe=P;const ie=be;const ue=he;const Ee=se;let ne=`M ${oe+(g?C:0)} ${ie}`;ne+=` L ${oe+ue-(m?C:0)} ${ie}`;if(m){ne+=` Q ${oe+ue} ${ie} ${oe+ue} ${ie+C}`}ne+=` L ${oe+ue} ${ie+Ee-(M?C:0)}`;if(M){ne+=` Q ${oe+ue} ${ie+Ee} ${oe+ue-C} ${ie+Ee}`}ne+=` L ${oe+(u?C:0)} ${ie+Ee}`;if(u){ne+=` Q ${oe} ${ie+Ee} ${oe} ${ie+Ee-C}`}ne+=` L ${oe} ${ie+(g?C:0)}`;if(g){ne+=` Q ${oe} ${ie} ${oe+C} ${ie}`}ne+=` Z`;const er=ke?oe:oe+ue;const fr=o/2;return c`<path d=${ne} fill=${r} stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
      <line x1=${er} x2=${er} y1=${ie+fr} y2=${ie+Ee-fr} stroke=${r} stroke-width=${o+.5} vector-effect="non-scaling-stroke"/>`}const A=e.hasBar?Re(e)?e.barThickness:-e.barThickness:0;let H=Go(e);let _=Re(e)?A:A-p;let S=d;let E=p;const D=e.side==="bottom";let K;let I;if(e.hasBar){if(D){K=_-1;I=_+E}else{K=_;I=_+E+1}}else{K=_;I=_+E}const Y=an(H,S,H,H+S,o);H=Y.x;S=Y.width;const R=nn(_,E,K,I,o);_=R.y;E=R.height;const B=H;const F=_;const z=S;const ee=E;let T=`M ${B+(g?C:0)} ${F}`;T+=` L ${B+z-(m?C:0)} ${F}`;if(m){T+=` Q ${B+z} ${F} ${B+z} ${F+C}`}T+=` L ${B+z} ${F+ee-(M?C:0)}`;if(M){T+=` Q ${B+z} ${F+ee} ${B+z-C} ${F+ee}`}T+=` L ${B+(u?C:0)} ${F+ee}`;if(u){T+=` Q ${B} ${F+ee} ${B} ${F+ee-C}`}T+=` L ${B} ${F+(g?C:0)}`;if(g){T+=` Q ${B} ${F} ${B+C} ${F}`}T+=` Z`;const Z=D?F:F+ee;const q=o/2;return c`<path d=${T} fill=${r} stroke=${a} stroke-width=${o} vector-effect="non-scaling-stroke"/>
    <line x1=${B+q} x2=${B+z-q} y1=${Z} y2=${Z} stroke=${r} stroke-width=${o+.5} vector-effect="non-scaling-stroke"/>`}function x7(e){if(xt(e)){return e.side==="right"?90:-90}return e.side==="bottom"?180:0}function qp(e,t,i,o,r,a,n=1,p=false){const d=Wd(`external-scale-setpoint-${a}`);const f=No(i);const g=Math.abs(t)<e.setpointAtZeroDeadband;const m=g?pt(e,0):pt(e,t);const u=dn(e);const M=Gl();const C=M+f;const A=Re(e)?u+C:u-C;const H=x7(e);const _=xt(e)?A:m;const S=xt(e)?m:A;if(p){const E=`var(${io}, ${ko})`;return c`
      <g style="transform: translate(${_}px, ${S}px) rotate(${H}deg); opacity: ${n}; transition: transform ${E} ease-out, opacity ${E} ease-out;">
        ${nr({visualState:i,colorMode:o,disabled:r,id:d})}
      </g>
    `}return c`
    <g transform="translate(${_}, ${S}) rotate(${H})" opacity="${n}">
      ${nr({visualState:i,colorMode:o,disabled:r,id:d})}
    </g>
  `}function $7(e){const t=e.setpoint!==void 0;const i=e.newSetpoint!==void 0;const o=e.departingNewSetpoint!==void 0;const r=e.animateSetpoint===true;if(!t&&!i&&!o)return w;const a=[];if(t){const n=m7(e);const p=Wp(e);const d=g7(e);const f=i?.75:1;a.push(qp(e,e.setpoint,n,p,d,"original",f,r))}if(i||o){const n=i;const p=n?e.newSetpoint:e.departingNewSetpoint;const d=n?1:0;const f=at.focus;const g=Wp(e);const m=false;a.push(qp(e,p,f,g,m,"new",d,r))}return c`${a}`}function M7(e){if(!e.highlightCurrentValue||e.value===void 0||!e.hasScale){return w}const t=12;const i=2;const o=t/2+i/2;const r=t/2;const a=pt(e,e.value);const n=dn(e);const p=Re(e)?n+o:n-o;const d=Xp(e);const f=d.markerFillColor;const g="var(--instrument-frame-primary-color)";if(xt(e)){return c`
      <circle
        cx=${p}
        cy=${a}
        r=${r}
        fill=${f}
        stroke=${g}
        stroke-width=${i}
        vector-effect="non-scaling-stroke"
      />
    `}return c`
    <circle
      cx=${a}
      cy=${p}
      r=${r}
      fill=${f}
      stroke=${g}
      stroke-width=${i}
      vector-effect="non-scaling-stroke"
    />
  `}function jl(e,t,i,o){if(t>=e.maxValue||t<=e.minValue)return null;const r=bi(i);const a=pt(e,t);const n=Gl();const p=Re(e)?o+n:o-n;const d=cn(e);const f=Re(e)?p+d:p-d;if(xt(e)){return c`<line x1=${p} x2=${f} y1=${a} y2=${a} stroke=${r} stroke-width="1" vector-effect="non-scaling-stroke"/>`}return c`<line x1=${a} x2=${a} y1=${p} y2=${f} stroke=${r} stroke-width="1" vector-effect="non-scaling-stroke"/>`}function _1(e,t,i,o,r){const a=8;const n=4;const p=a/2;const d=4;if(xt(e)){const H=pt(e,t.min);const _=pt(e,t.max);const S=Math.min(H,_);const E=Math.max(H,_);const D=i+n;const K=S+d;const I=Math.max(0,E-S-d*2);return c`<rect x=${D} y=${K} width=${a} height=${I} rx=${p} ry=${p} fill=${o} stroke=${r} stroke-width="1" vector-effect="non-scaling-stroke"/>`}const f=pt(e,t.min);const g=pt(e,t.max);const m=Math.min(f,g);const u=Math.max(f,g);const M=m+d;const C=i+n;const A=Math.max(0,u-m-d*2);return c`<rect x=${M} y=${C} width=${A} height=${a} rx=${p} ry=${p} fill=${o} stroke=${r} stroke-width="1" vector-effect="non-scaling-stroke"/>`}function H7(e,t){const i=dn(e);const o=e.hasBar;const r=o?e.advicePosition:"inner";let a;if(r==="center"){const H=8;const _=e.barThickness/2-H/2;if(xt(e)){a=Re(e)?_-4:-e.barThickness+_-4}else{a=Re(e)?_-4:-e.barThickness+_-4}}else if(r==="inner"){a=Re(e)?i:i-16}else{a=Re(e)?e.barThickness+10:-e.barThickness-cn(e)+14}const n=[];const p="var(--instrument-frame-tertiary-color)";const d=t.min>e.minValue;const f=t.max<e.maxValue;const g=Re(e)?0:-e.barThickness;const m=Re(e)?e.barThickness:0;const u=H=>{const _=pt(e,H);if(xt(e)){n.push(c`<line x1=${g} x2=${m} y1=${_} y2=${_} stroke=${p} stroke-width="1" vector-effect="non-scaling-stroke" stroke-dasharray="4 4"/>`)}else{n.push(c`<line x1=${_} x2=${_} y1=${g} y2=${m} stroke=${p} stroke-width="1" vector-effect="non-scaling-stroke" stroke-dasharray="4 4"/>`)}};if(d)u(t.min);if(f)u(t.max);if(t.type===dt.caution){let H;let _="var(--instrument-frame-primary-color)";if(t.state===de.hinted){H="var(--instrument-frame-tertiary-color)"}else if(t.state===de.regular){H="var(--instrument-tick-mark-tertiary-color)"}else{H="var(--on-caution-active-color)";_="var(--alert-caution-color)"}const S=[];const E=50;const D=pt(e,t.min);const K=pt(e,t.max);const I=Math.min(D,K);const Y=Math.max(D,K);const R=Y-I;if(xt(e)){const z=a+8-25;const ee=I-25;for(let T=-64;T<R+64;T+=16){const Z=`translate(${z} ${ee+T})`;const q=`M 50 0 L 0 ${E}`;S.push(c`<g transform=${Z}><path d=${q} stroke=${H} stroke-width="6"/></g>`)}}else{const z=a+8-25;const ee=I-25;for(let T=-64;T<R+64;T+=16){const Z=`translate(${ee+T} ${z})`;const q=`M 0 50 L ${E} 0`;S.push(c`<g transform=${Z}><path d=${q} stroke=${H} stroke-width="6"/></g>`)}}const B=`externalScaleAdviceMask-${t.min}-${t.max}-${Math.random().toString(36).slice(2)}`;let F=He.regular;if(t.state===de.regular)F=He.regular;else if(t.state===de.triggered)F=He.enhanced;return c`
      <defs>
        <mask id=${B} maskUnits="userSpaceOnUse" maskContentUnits="userSpaceOnUse" x="-4096" y="-4096" width="8192" height="8192">
          ${_1(e,t,a,"white","none")}
        </mask>
      </defs>
      <g mask="url(#${B})">
        ${_?c`<rect x="-2048" y="-2048" width="4096" height="4096" fill=${_}/>`:w}
        ${S}
      </g>
      ${_1(e,t,a,"none",H)}
      ${jl(e,t.min,F,i)??w}
      ${jl(e,t.max,F,i)??w}
      ${n}
    `}let M;let C;let A;if(t.state===de.hinted){M="var(--instrument-frame-tertiary-color)";A="var(--instrument-frame-primary-color)";C=He.regular}else if(t.state===de.regular){M="var(--instrument-regular-secondary-color)";A="var(--instrument-frame-primary-color)";C=He.regular}else{M="var(--instrument-enhanced-secondary-color)";A=M;C=He.regular}return c`
    ${_1(e,t,a,A,M)}
    ${jl(e,t.min,C,i)??w}
    ${jl(e,t.max,C,i)??w}
    ${n}
  `}function S7(e){if(!e.advices||!e.advices.length)return[];const t=b7(e.advices,e.setpoint);return t.map(i=>H7(e,i))}function e0(e){const t=T1(e);const i=Z1({orientation:e.orientation,length:e.length},t);const o=e.orientation==="vertical"?i.width:i.height;return{side:e.side,thickness:o}}function t0(e){const t=Fl(e);const i=t===e.barThickness?e:{...e,barThickness:t};const o={barContainer:C7(i),barFill:k7(i),scaleBackground:L7(i),tickmarks:y7(i),labels:w7(i),adviceOverlays:S7(i),currentValueDot:M7(i),setpoint:$7(i)};return o}var _7=Object.defineProperty;var ho=(e,t,i,o)=>{var r=void 0;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=n(t,i,r)||r;if(r)_7(t,i,r);return r};function qo(e,t){const{defaultDeadband:i=2,defaultZeroDeadband:o=.5,angularWraparound:r=false}=t??{};class a extends e{constructor(){super(...arguments);this.atSetpoint=false;this.touching=false;this.autoAtSetpoint=true;this.autoAtSetpointDeadband=i;this.setpointAtZeroDeadband=o;this.setpointOverride=false;this.animateSetpoint=false}get departingNewSetpoint(){return this._departingNewSetpoint}computeAtSetpoint(p){return aa({value:p,setpoint:this.setpoint,touching:this.touching,auto:this.autoAtSetpoint,deadband:this.autoAtSetpointDeadband,atSetpointManual:this.atSetpoint,angularWraparound:r})}willUpdate(p){super.willUpdate(p);if(p.has("newSetpoint")&&this.animateSetpoint){const d=p.get("newSetpoint");if(d!==void 0&&this.newSetpoint===void 0){this._departingNewSetpoint=d;clearTimeout(this._animationTimer);const f=cl(this);this._animationTimer=setTimeout(()=>{this._departingNewSetpoint=void 0},f)}}}disconnectedCallback(){super.disconnectedCallback();clearTimeout(this._animationTimer)}}ho([l({type:Number})],a.prototype,"setpoint");ho([l({type:Number})],a.prototype,"newSetpoint");ho([l({type:Boolean,attribute:false})],a.prototype,"atSetpoint");ho([l({type:Boolean})],a.prototype,"touching");ho([l({type:Boolean,attribute:false})],a.prototype,"autoAtSetpoint");ho([l({type:Number})],a.prototype,"autoAtSetpointDeadband");ho([l({type:Number})],a.prototype,"setpointAtZeroDeadband");ho([l({type:Boolean})],a.prototype,"setpointOverride");ho([l({type:Boolean})],a.prototype,"animateSetpoint");ho([Ve()],a.prototype,"_departingNewSetpoint");return a}var V7=Object.defineProperty;var A7=Object.getOwnPropertyDescriptor;var Se=(e,t,i,o)=>{var r=o>1?void 0:o?A7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)V7(t,i,r);return r};var Me=class extends qo(k,{defaultDeadband:1}){constructor(){super(...arguments);this.minValue=0;this.maxValue=100;this.width=320;this.paddingLeft=H1.CANVAS_PADDING;this.paddingRight=H1.CANVAS_PADDING;this.side=ln.bottom;this.fixedAspectRatio=false;this.scaleReferenceSize=384;this._scale=1;this._resizeController=new Lo(this,{callback:e=>{if(!this.fixedAspectRatio)return;const t=e[0];if(!t)return;const i=t.contentRect.width;this._scale=Ul({orientation:Mi.horizontal,containerMainAxisSize:i,scaleReferenceSize:this.scaleReferenceSize});this.reportDimensions()}});this.hasScale=true;this.showLabels=true;this.hasBar=false;this.scaleBackground=false;this.barContainerStyle=void 0;this.barThickness=24;this.tickThickness=24;this.labelThickness=60;this.mainTickmarks=[];this.primaryTickmarkInterval=void 0;this.secondaryTickmarkInterval=void 0;this.tertiaryTickmarkInterval=void 0;this.scaleType=Hi.regular;this.frameStyle=Wa.regular;this.borderRadiusPosition=void 0;this.instrumentMode=false;this.borderRadius=void 0;this._borderRadiusResizeController=new Lo(this,{callback:()=>{if(!this.instrumentMode){this._refreshBorderRadiusFromCssVar()}}});this.priority=me.regular;this.fillMode=sn.fill;this.fillMin=void 0;this.fillMax=void 0;this.value=void 0;this.state=Le.active;this.advicePosition=A1.inner;this.advices=[];this.highlightCurrentValue=false}render(){const e=this.fixedAspectRatio?this.scaleReferenceSize:this.width;const t={orientation:Mi.horizontal,side:this.side,length:e,paddingStart:this.paddingLeft,paddingEnd:this.paddingRight,minValue:this.minValue,maxValue:this.maxValue,hasScale:this.hasScale,labels:this.showLabels,hasBar:this.hasBar,scaleBackground:this.scaleBackground,barContainerStyle:this.barContainerStyle,barThickness:this.barThickness,tickThickness:this.tickThickness,labelThickness:this.labelThickness,borderRadius:this._getEffectiveBorderRadius(),mainTickmarks:this.mainTickmarks,primaryTickmarkInterval:this.primaryTickmarkInterval,secondaryTickmarkInterval:this.secondaryTickmarkInterval,tertiaryTickmarkInterval:this.tertiaryTickmarkInterval,scaleType:this.scaleType,frameStyle:this.frameStyle,borderRadiusPosition:this.borderRadiusPosition,priority:this.priority,setpointOverride:this.setpointOverride,fillMode:this.fillMode,fillMin:this.fillMin,fillMax:this.fillMax,value:this.value,setpoint:this.setpoint,newSetpoint:this.newSetpoint,atSetpoint:this.atSetpoint,autoAtSetpoint:this.autoAtSetpoint,autoAtSetpointDeadband:this.autoAtSetpointDeadband,setpointAtZeroDeadband:this.setpointAtZeroDeadband,animateSetpoint:this.animateSetpoint,departingNewSetpoint:this.departingNewSetpoint,state:this.state,touching:this.touching,advicePosition:this.advicePosition,advices:this.advices,fixedAspectRatio:this.fixedAspectRatio,instrumentMode:this.instrumentMode,highlightCurrentValue:this.highlightCurrentValue};const i=T1(Kp(t));const o=t0(t);const r=Z1({orientation:t.orientation,length:e},i);const a=this.fixedAspectRatio?"xMidYMid meet":"none";return h`
      <svg
        width=${this.fixedAspectRatio?"100%":`${this.width}px`}
        height=${this.fixedAspectRatio?"100%":`${r.height}px`}
        viewBox="${r.x} ${r.y} ${r.width} ${r.height}"
        preserveAspectRatio="${a}"
        style="--scale: ${this.fixedAspectRatio?this._scale:1};"
        part="svg"
      >
        ${o.barContainer} ${o.barFill} ${o.scaleBackground}
        ${o.tickmarks} ${o.labels} ${o.adviceOverlays}
        ${o.currentValueDot} ${o.setpoint}
      </svg>
    `}updated(e){super.updated(e);if(e.has("scaleType")){this._refreshBorderRadiusFromCssVar()}if(e.has("fixedAspectRatio")){if(this.fixedAspectRatio){this._applyFixedAspectRatioStyles();this._updateScaleFromCurrentSize()}else{this._removeFixedAspectRatioStyles();this._scale=1}}if(e.has("scaleReferenceSize")&&this.fixedAspectRatio){this._updateScaleFromCurrentSize()}const t=e.has("side")||e.has("showLabels")||e.has("hasScale")||e.has("hasBar")||e.has("barThickness")||e.has("tickThickness")||e.has("labelThickness")||e.has("scaleType")||e.has("borderRadiusPosition")||e.has("borderRadius");if(!this.fixedAspectRatio||t){this.reportDimensions()}}reportDimensions(){const e=Fl({hasBar:this.hasBar,barThickness:this.barThickness,borderRadius:this._getEffectiveBorderRadius(),scaleType:this.scaleType});const t=this.fixedAspectRatio?this.scaleReferenceSize:this.width;const i=e0({orientation:Mi.horizontal,side:this.side,hasBar:this.hasBar,hasScale:this.hasScale,labels:this.showLabels,barThickness:e,tickThickness:this.tickThickness,labelThickness:this.labelThickness,length:t,scaleType:this.scaleType});const o=this.fixedAspectRatio?{...i,thickness:Math.round(i.thickness*this._scale)}:i;this.dispatchEvent(new CustomEvent("scale-dimensions-changed",{detail:o,bubbles:true,composed:true}))}createRenderRoot(){return this}connectedCallback(){super.connectedCallback();if(!this.instrumentMode){this._refreshBorderRadiusFromCssVar();this._startBorderRadiusObserver()}if(this.fixedAspectRatio){this._applyFixedAspectRatioStyles()}}disconnectedCallback(){this._borderRadiusObserver?.disconnect();this._borderRadiusObserver=void 0;super.disconnectedCallback()}_startBorderRadiusObserver(){this._borderRadiusObserver?.disconnect();this._borderRadiusObserver=Qp(this,()=>this._refreshBorderRadiusFromCssVar())}_applyFixedAspectRatioStyles(){this.style.display="block";this.style.width="100%";this.style.height="auto"}_removeFixedAspectRatioStyles(){this.style.display="";this.style.width="";this.style.height=""}_updateScaleFromCurrentSize(){requestAnimationFrame(()=>{const e=this.clientWidth;if(e>0){this._scale=Ul({orientation:Mi.horizontal,containerMainAxisSize:e,scaleReferenceSize:this.scaleReferenceSize});this.requestUpdate();this.reportDimensions()}})}_refreshBorderRadiusFromCssVar(){if(this.instrumentMode)return;const e=Yp(this,this.scaleType);if(this._computedBorderRadius!==e){this._computedBorderRadius=e}if(this.fixedAspectRatio){const t=this.getBoundingClientRect();if(t.width>0){this._scale=Ul({orientation:Mi.horizontal,containerMainAxisSize:t.width,scaleReferenceSize:this.scaleReferenceSize});this.reportDimensions()}}}_getEffectiveBorderRadius(){if(this.instrumentMode){if(this.borderRadius!==void 0){return this.borderRadius}return this.scaleType===Hi.condensed?4:8}return this._computedBorderRadius??(this.scaleType===Hi.condensed?4:8)}};Se([l({type:Number})],Me.prototype,"minValue",2);Se([l({type:Number})],Me.prototype,"maxValue",2);Se([l({type:Number})],Me.prototype,"width",2);Se([l({type:Number})],Me.prototype,"paddingLeft",2);Se([l({type:Number})],Me.prototype,"paddingRight",2);Se([l({type:String})],Me.prototype,"side",2);Se([l({type:Boolean})],Me.prototype,"fixedAspectRatio",2);Se([l({type:Number})],Me.prototype,"scaleReferenceSize",2);Se([Ve()],Me.prototype,"_scale",2);Se([l({type:Boolean,attribute:false})],Me.prototype,"hasScale",2);Se([l({type:Boolean,attribute:false})],Me.prototype,"showLabels",2);Se([l({type:Boolean})],Me.prototype,"hasBar",2);Se([l({type:Boolean})],Me.prototype,"scaleBackground",2);Se([l({type:String})],Me.prototype,"barContainerStyle",2);Se([l({type:Number})],Me.prototype,"barThickness",2);Se([l({type:Number})],Me.prototype,"tickThickness",2);Se([l({type:Number})],Me.prototype,"labelThickness",2);Se([l({attribute:false})],Me.prototype,"mainTickmarks",2);Se([l({type:Number})],Me.prototype,"primaryTickmarkInterval",2);Se([l({type:Number})],Me.prototype,"secondaryTickmarkInterval",2);Se([l({type:Number})],Me.prototype,"tertiaryTickmarkInterval",2);Se([l({type:String})],Me.prototype,"scaleType",2);Se([l({type:String})],Me.prototype,"frameStyle",2);Se([l({type:String})],Me.prototype,"borderRadiusPosition",2);Se([l({type:Boolean})],Me.prototype,"instrumentMode",2);Se([l({type:Number})],Me.prototype,"borderRadius",2);Se([Ve()],Me.prototype,"_computedBorderRadius",2);Se([l({type:String})],Me.prototype,"priority",2);Se([l({type:String})],Me.prototype,"fillMode",2);Se([l({type:Number})],Me.prototype,"fillMin",2);Se([l({type:Number})],Me.prototype,"fillMax",2);Se([l({type:Number})],Me.prototype,"value",2);Se([l({type:String})],Me.prototype,"state",2);Se([l({type:String})],Me.prototype,"advicePosition",2);Se([l({attribute:false})],Me.prototype,"advices",2);Se([l({type:Boolean})],Me.prototype,"highlightCurrentValue",2);Me=Se([x("obc-bar-horizontal")],Me);function*r0(e,t){if(void 0!==e){let i=0;for(const o of e)yield t(o,i++)}}var Z7=Object.defineProperty;var T7=Object.getOwnPropertyDescriptor;var Qt=(e,t,i,o)=>{var r=o>1?void 0:o?T7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Z7(t,i,r);return r};function Tt(e,t){if(e.cssPart){return`${e.cssPart} ${t}`}return void 0}var Pt=class extends k{constructor(){super(...arguments);this.data=[];this.columns=[];this.rowDivider=false;this.narrowHeader=false;this.showHeader=true;this.striped=false;this.selectable=false;this.selectAllAriaLabel="Select all rows";this._sortByColumnIdx=void 0;this._sortDirection="asc";this._selectedRowIds=new Set;this._previousPositions=[];this._hasRenderedRows=false}get sortedData(){if(this._sortByColumnIdx===void 0){return this.data}const e=this.columns[this._sortByColumnIdx];if(e===void 0){console.warn("Sort by column is undefined");return this.data}const t=this._sortDirection;const i=[...this.data];i.sort((o,r)=>{const a=o[e.key];const n=r[e.key];if(t==="asc"){return e.compareFunction(a,n,o,r)}else{return e.compareFunction(n,a,r,o)}});return i}_handleSortClick(e){if(!e.sortable){return}const t=this.columns.indexOf(e);if(t===this._sortByColumnIdx){this._sortDirection=this._sortDirection==="asc"?"desc":"asc"}else{this._sortByColumnIdx=t;this._sortDirection="asc"}}_handleRowClick(e){this.dispatchEvent(new CustomEvent("row-click",{detail:{row:e}}))}_focusFirstRow(){const e=this.renderRoot.querySelector('button[role="row"].grid-row');e?.focus()}_focusLeftHeaderItem(){this._focusHeaderByIndex(0)}_focusHeaderByIndex(e){const t=Array.from(this.renderRoot.querySelectorAll('.grid-header [role="columnheader"]'));if(t.length===0)return;const i=Math.max(0,Math.min(e,t.length-1));const o=t[i];const r=o.shadowRoot?.querySelector("button")??null;(r??o).focus()}_handleHeaderKeyDown(e){const t=e.key;if(t==="ArrowDown"){this._focusFirstRow();e.preventDefault();e.stopPropagation();return}if(t!=="ArrowLeft"&&t!=="ArrowRight"){return}const i=Array.from(this.renderRoot.querySelectorAll('.grid-header [role="columnheader"]'));if(i.length===0)return;const o=e.currentTarget;const r=o?i.indexOf(o):-1;if(r===-1)return;const a=t==="ArrowRight"?Math.min(r+1,i.length-1):Math.max(r-1,0);if(a!==r){this._focusHeaderByIndex(a);e.preventDefault();e.stopPropagation()}}_handleRowKeyDown(e){const t=e.key;if(t!=="ArrowDown"&&t!=="ArrowUp"&&t!=="Home"&&t!=="End"){return}const i=e.currentTarget;if(!i)return;const o=Array.from(this.renderRoot.querySelectorAll('button[role="row"].grid-row'));const r=o.indexOf(i);if(r===-1)return;let a=r;switch(t){case"ArrowDown":a=Math.min(r+1,o.length-1);break;case"ArrowUp":if(r===0){this._focusLeftHeaderItem();e.preventDefault();e.stopPropagation();return}a=Math.max(r-1,0);break;case"Home":a=0;break;case"End":a=o.length-1;break}if(a!==r){o[a]?.focus();e.preventDefault();e.stopPropagation()}else if(t==="Home"||t==="End"){e.preventDefault();e.stopPropagation()}}_getAllPositions(){const e=Array.from(this.renderRoot.querySelectorAll('button[role="row"].grid-row'));const t=e[0];if(!t){return[]}const i=t.getBoundingClientRect();const o=i.height;const r=getComputedStyle(t);const a=parseFloat(r.height);const n=a/o;return e.map(p=>{const d=p.getBoundingClientRect();return{top:d.top*n,height:d.height*n,index:p.getAttribute("data-row-id")??"",element:p}})}_animateRowChanges(){const e=this._previousPositions;const t=this._getAllPositions();t.forEach(i=>{const o=e.find(r=>r.index===i.index);if(!o){i.element.style.transform=`translateY(-${i.height}px)`;i.element.style.opacity="0"}else{i.element.style.transform=`translateY(${o.top-i.top}px)`}i.element.style.transition="none";i.element.offsetHeight;i.element.style.transition="transform 100ms ease-in-out, opacity 100ms ease-in-out";i.element.style.transform="translateY(0px)";i.element.style.opacity="1"});this._previousPositions=t}willUpdate(e){if(e.has("defaultSelectedRowIds")){if(this.selectedRowIds===void 0&&this._selectedRowIds.size===0){this._selectedRowIds=new Set(this.defaultSelectedRowIds??[])}}if(e.has("selectedRowIds")){if(this.selectedRowIds!==void 0){this._selectedRowIds=new Set(this.selectedRowIds)}}if(e.has("data")){const t=new Set(this.data.map(i=>i.id));this._selectedRowIds.forEach(i=>{if(!t.has(i)){this._selectedRowIds.delete(i)}})}if(e.has("data")||e.has("_sortByColumnIdx")||e.has("_sortDirection")){if(this._hasRenderedRows){this._updatePositions()}else{this.updateComplete.then(()=>{this._hasRenderedRows=true})}}}updated(e){if(e.has("columns")){this._sortByColumnIdx=this.columns.findIndex(t=>"sortDirection"in t&&t.sortDirection!==void 0);if(this._sortByColumnIdx===-1){this._sortByColumnIdx=void 0;this._sortDirection="asc"}else{this._sortDirection=this.columns[this._sortByColumnIdx]?.sortDirection??"asc"}}if(e.has("data")||e.has("_sortByColumnIdx")||e.has("_sortDirection")){if(this._hasRenderedRows){this._animateRowChanges()}}}_updatePositions(){const e=this._getAllPositions();this._previousPositions=e}render(){const e=this.selectable?[{label:"",key:"__selection__"},...this.columns]:this.columns;const t=this.selectable?Math.max(0,e.length-1):e.length;return h`
      <div
        class=${J({"grid-container":true,"has-selection-column":this.selectable})}
        part="grid"
        style="
          --grid-columns: ${e.length};
          --grid-columns-rest: ${t};
          --selection-column-width: var(--menu-navigation-components-table-item-touch-target-size);
        "
        role="table"
      >
        ${this.showHeader?h`
              <div class="grid-header" role="row">
                ${e.map(i=>{const o=this.selectable&&i.key==="__selection__";const r=e.indexOf(i)!==e.length-1;const a=i.renderHeaderIcon?h`<span slot="leading-icon"
                        >${i.renderHeaderIcon()}</span
                      >`:w;const n=this.columns.findIndex(g=>g.key===i.key);const p="sortable"in i&&i.sortable&&this._sortByColumnIdx===n;const d=p?this._sortDirection:"none";const f=i.headerType??(this.narrowHeader?El.Narrow:El.Regular);if("sortable"in i&&i.sortable&&!o){return h`<obc-table-header-item
                      role="columnheader"
                      class=${o?"selection-header":""}
                      .showDivider=${r}
                      ?hasLeadingIcon=${a!==w}
                      .sortDirection=${d}
                      .sortable=${true}
                      type=${f}
                      @click=${()=>this._handleSortClick(i)}
                      @keydown=${this._handleHeaderKeyDown}
                      >${a}${i.label}</obc-table-header-item
                    > `}else{if(o){return h`<div
                        role="columnheader"
                        class=${J({"selection-header":true})}
                        tabindex="0"
                        @keydown=${this._handleHeaderKeyDown}
                      >
                        <obc-checkbox
                          .status=${this._getSelectionStatus()}
                          .disabled=${false}
                          aria-label=${this.selectAllAriaLabel}
                          @click=${g=>{g.preventDefault();g.stopPropagation()}}
                          @change=${()=>this._toggleAllSelection()}
                        ></obc-checkbox>
                      </div>`}return h`<obc-table-header-item
                      role="columnheader"
                      class=${o?"selection-header":""}
                      .showDivider=${r}
                      ?hasLeadingIcon=${a!==w}
                      type=${f}
                      >${a}${i.label}</obc-table-header-item
                    >`}})}
              </div>
              <div class="grid-header-divider"></div>
            `:w}
        <div
          class="grid-body"
          part="body"
          style="grid-template-rows: repeat(${this.sortedData.length}, min-content)"
        >
          ${rn(this.sortedData,i=>i.id,(i,o)=>{const r=this.rowDivider&&this.data.length-1!==o;const a=this.striped&&o%2===1;const n=(i.selected??false)||this.selectable&&this._selectedRowIds.has(i.id);const p=o>0?this.sortedData[o-1]:void 0;const d=o<this.sortedData.length-1?this.sortedData[o+1]:void 0;const f=p!==void 0&&((p.selected??false)||this.selectable&&this._selectedRowIds.has(p.id));const g=d!==void 0&&((d.selected??false)||this.selectable&&this._selectedRowIds.has(d.id));return h`
                <button
                  role="row"
                  class=${J({"grid-row":true,selected:n,"selected-with-prev":n&&f,"selected-with-next":n&&g,striped:a})}
                  @click=${()=>this._handleRowClick(i)}
                  @keydown=${this._handleRowKeyDown}
                  data-row-id=${i.id}
                  style="grid-row: ${o+1}"
                  part="row"
                >
                  ${r0(e,m=>{if(this.selectable&&m.key==="__selection__"){const M=this._selectedRowIds.has(i.id);return h`<div
                        class="grid-cell checkbox align-center selection"
                        role="cell"
                      >
                        <obc-checkbox
                          .status=${M?po.checked:po.unchecked}
                          .disabled=${false}
                          aria-label=${`Select row ${i.id}`}
                          @click=${C=>{C.preventDefault();C.stopPropagation()}}
                          @change=${()=>this._toggleRowSelection(i.id)}
                        ></obc-checkbox>
                      </div>`}const u=i[m.key];if(u===void 0){return h`<div class="grid-cell" role="cell"></div>`}if(m.renderCell){return h`<div
                        class="grid-cell ${m.dividerRight?"divider-right":""}"
                        role="cell"
                        part=${$e(u.cssPart)}
                      >
                        ${m.renderCell(u,i,i.id)}
                      </div>`}else{return this._renderCell(u,i,m)}})}
                  ${r?h`<div class="grid-row-divider"></div>`:w}
                </button>
              `})}
          ${rn(e,i=>i.key,(i,o)=>i.dividerRight?h`<div
                    class="grid-column-divider"
                    style="grid-column: ${o+1}; grid-row: 1/${this.sortedData.length+1}"
                  ></div>`:w)}
        </div>
      </div>
    `}getAllVisibleRows(){const e=Array.from(this.renderRoot.querySelectorAll('button[role="row"].grid-row'));const t=this.renderRoot.querySelector(".grid-body")?.getBoundingClientRect();if(!t){return[]}const i=t.top;const o=t.height;const r=i+o;return e.filter(a=>a.checkVisibility()).filter(a=>a.getBoundingClientRect().top>=i&&a.getBoundingClientRect().bottom<=r).map(a=>a.getAttribute("data-row-id")).filter(a=>a!==null)}_handleCellButtonClick(e,t,i){e.preventDefault();e.stopPropagation();const o=new CustomEvent("cell-button-click",{detail:{rowId:t.id,columnKey:i}});this.dispatchEvent(o)}_handleCellTagClick(e,t,i,o){e.preventDefault();e.stopPropagation();const r=new CustomEvent("cell-tag-click",{detail:{rowId:t.id,columnKey:i,tagId:o}});this.dispatchEvent(r)}_handleCellCheckboxChange(e,t,i){e.preventDefault();e.stopPropagation();const o=new CustomEvent("cell-checkbox-change",{detail:{rowId:t.id,columnKey:i,status:e.detail.status,disabled:e.detail.disabled}});this.dispatchEvent(o)}_getSelectableRowIds(){return this.data.map(e=>e.id)}_getSelectionStatus(){const e=this._getSelectableRowIds();if(e.length===0)return po.unchecked;const t=e.filter(i=>this._selectedRowIds.has(i)).length;if(t===0)return po.unchecked;if(t===e.length)return po.checked;return po.mixed}_emitSelectionChange(e,t){const i=this.data.filter(r=>e.includes(r.id));const o=new CustomEvent("selection-change",{detail:{selectedRowIds:e,selectedRows:i,source:t}});this.dispatchEvent(o)}_applySelectionChange(e,t){const i=Array.from(e);this._emitSelectionChange(i,t);if(this.selectedRowIds===void 0){this._selectedRowIds=e;this.requestUpdate()}}_toggleRowSelection(e){const t=new Set(this._selectedRowIds);if(t.has(e)){t.delete(e)}else{t.add(e)}this._applySelectionChange(t,"row")}_toggleAllSelection(){const e=this._getSelectableRowIds();const t=this._getSelectionStatus();const i=t===po.checked?new Set:new Set(e);this._applySelectionChange(i,"header")}_renderCell(e,t,i){if(e.type==="regular"){return h`<div
        class=${J({"grid-cell":true,regular:true,neutral:e.neutral??false,"large-icon":e.largeIcon??false,"no-wrap":e.noWrap??false,[`align-${e.align??"left"}`]:true,"divider-right":i.dividerRight??false,vertical:e.vertical??false})}
        role="cell"
        part=${$e(Tt(e,"cell"))}
      >
        ${e.icon3?h`<span class="icon" part=${$e(Tt(e,"icon3"))}
              >${e.icon3}</span
            >`:w}
        ${e.icon2?h`<span class="icon" part=${$e(Tt(e,"icon2"))}
              >${e.icon2}</span
            >`:w}
        ${e.icon?h`<span class="icon" part=${$e(Tt(e,"icon"))}
              >${e.icon}</span
            >`:w}
        ${e.title?h`<span class="title" part=${$e(Tt(e,"title"))}
              >${e.title}</span
            >`:w}
        ${e.text?h`<span part=${$e(Tt(e,"text"))}
              >${e.text}</span
            >`:w}
      </div>`}else if(e.type==="button"){return h`<div
        class="grid-cell button ${i.dividerRight?"divider-right":""}"
        role="cell"
      >
        <obc-button
          variant="normal"
          fullWidth
          ?showLeadingIcon=${e.icon!==void 0}
          part=${$e(Tt(e,"button"))}
          @click=${o=>this._handleCellButtonClick(o,t,i.key)}
        >
          ${e.icon?h`<span
                slot="leading-icon"
                part=${$e(Tt(e,"icon"))}
                >${e.icon}</span
              >`:w}
          ${e.text?h`<span part=${$e(Tt(e,"text"))}
                >${e.text}</span
              >`:w}
        </obc-button>
      </div>`}else if(e.type==="checkbox"){const o=e.label??e.text??"";const r=o.trim()||i.label?.trim()||"Checkbox";return h`<div
        class=${J({"grid-cell":true,checkbox:true,[`align-${e.align??"center"}`]:true,"divider-right":i.dividerRight??false})}
        role="cell"
        part=${$e(Tt(e,"cell"))}
      >
        <obc-checkbox
          .status=${e.status??po.unchecked}
          .disabled=${e.disabled??false}
          aria-describedby=${$e(e.ariaDescribedBy)}
          aria-label=${r}
          part=${$e(Tt(e,"checkbox"))}
          @click=${a=>{a.preventDefault();a.stopPropagation()}}
          @change=${a=>this._handleCellCheckboxChange(a,t,i.key)}
        ></obc-checkbox>
      </div>`}else if(e.type==="tag"){const o=e.tags??(e.tag?[e.tag]:void 0)??[{id:e.tagId??"tag",label:e.label??e.text??"Label",color:e.color,hasIcon:e.hasIcon,icon:e.icon}];const r=e.wrap??e.tags!==void 0;const a=e.tags?2:void 0;const n=(e.maxTags??a)!==void 0?Math.max(0,Math.floor(e.maxTags??a??0)):void 0;const p=n!==void 0?o.slice(0,n):o;const d=n!==void 0?Math.max(0,o.length-n):0;const f=e.overflowLabel??`+${d.toString()}`;return h`<div
        class=${J({"grid-cell":true,tags:o.length>1,wrap:r,[`align-${e.align??"left"}`]:true,"divider-right":i.dividerRight??false})}
        role="cell"
        part=${$e(Tt(e,"cell"))}
      >
        ${p.map(g=>{const m=g.hasIcon??g.icon!==void 0;return h`<obc-tag
            .label=${g.label}
            color=${g.color??M1.gray}
            ?hasIcon=${m}
            part=${$e([Tt(e,"tag"),g.cssPart].filter(Boolean).join(" ")||void 0)}
            @click=${u=>this._handleCellTagClick(u,t,i.key,g.id)}
          >
            ${m&&g.icon?g.icon:w}
          </obc-tag>`})}
        ${d>0?h`<span
              class="tag-overflow"
              part=${$e(Tt(e,"tag-overflow"))}
              >${f}</span
            >`:w}
      </div>`}else if(e.type==="horizontal-bar"){const o=e.hasBar??true;const r=e.hasScale??false;const a=!(e.hideLabels??true);const n=e.fixedAspectRatio??true;return h`<div
        class=${J({"grid-cell":true,"horizontal-bar":true,[`align-${e.align??"left"}`]:true,"divider-right":i.dividerRight??false})}
        role="cell"
        part=${$e(Tt(e,"cell"))}
      >
        <obc-bar-horizontal
          .minValue=${e.minValue??0}
          .maxValue=${e.maxValue??100}
          .value=${e.value}
          .setpoint=${e.setpoint}
          .hasBar=${o}
          .hasScale=${r}
          .showLabels=${a}
          .priority=${e.priority??me.regular}
          .fillMode=${e.fillMode??sn.fill}
          .fillMin=${e.fillMin}
          .fillMax=${e.fillMax}
          .barThickness=${e.barThickness??24}
          .scaleType=${e.scaleType??Hi.regular}
          .frameStyle=${e.frameStyle??Wa.regular}
          .side=${e.side??ln.bottom}
          .state=${e.state??Le.active}
          .fixedAspectRatio=${n}
          .scaleReferenceSize=${e.scaleReferenceSize??384}
          part=${$e(Tt(e,"bar"))}
        ></obc-bar-horizontal>
      </div>`}else{return w}}};Pt.styles=Q(zp);Qt([l({type:Array})],Pt.prototype,"data",2);Qt([l({type:Array})],Pt.prototype,"columns",2);Qt([l({type:Boolean})],Pt.prototype,"rowDivider",2);Qt([l({type:Boolean})],Pt.prototype,"narrowHeader",2);Qt([l({type:Boolean,attribute:false})],Pt.prototype,"showHeader",2);Qt([l({type:Boolean})],Pt.prototype,"striped",2);Qt([l({type:Boolean})],Pt.prototype,"selectable",2);Qt([l({type:Array})],Pt.prototype,"selectedRowIds",2);Qt([l({type:Array})],Pt.prototype,"defaultSelectedRowIds",2);Qt([l({type:String})],Pt.prototype,"selectAllAriaLabel",2);Qt([Ve()],Pt.prototype,"_sortByColumnIdx",2);Qt([Ve()],Pt.prototype,"_sortDirection",2);Qt([Ve()],Pt.prototype,"_selectedRowIds",2);Pt=Qt([x("obc-table")],Pt);var o0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: inline-block;
}

.wrapper {
  position: relative;
  user-select: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: var(--app-components-notification-button-touch-target-size);
  min-width: var(--app-components-notification-button-touch-target-size);
  padding: 0;
  margin: 0;
  border: none;
  background: none;
  box-sizing: border-box;
  cursor: pointer;
  transition: all 0.2s ease-in-out;
}

/* Flat style - when no counter */

.wrapper.flat {
            cursor: pointer;
}

.wrapper.flat:focus {
            outline: none;
}

.wrapper.flat .visible-wrapper {
            border-color: var(--flat-enabled-border-color);
            background-color: var(--flat-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--flat-enabled-border-color);
            --base-background-color: var(--flat-enabled-background-color);
}

.wrapper.flat.activated .visible-wrapper {
            border-color: var(--flat-activated-border-color);
            background-color: var(--flat-activated-background-color);
            --base-border-color: var(--flat-activated-border-color);
            --base-background-color: var(--flat-activated-background-color);
}

@media (hover:hover) {

.wrapper.flat:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--flat-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--flat-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.flat:active .visible-wrapper {
            border-color: var(--flat-pressed-border-color);
            background-color: var(--flat-pressed-background-color);
}

.wrapper.flat:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.flat:disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.flat.disabled .visible-wrapper {
            border-color: var(--flat-disabled-border-color);
            background-color: var(--flat-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-flat-disabled-color) !important;
}

.wrapper.flat:disabled {
            cursor: not-allowed;
}

.wrapper.flat.disabled {
            cursor: not-allowed;
}

/* Normal style - when has counter */

.wrapper.normal {
            cursor: pointer;
}

.wrapper.normal:focus {
            outline: none;
}

.wrapper.normal .visible-wrapper {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.wrapper.normal.activated .visible-wrapper {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.wrapper.normal:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.normal:active .visible-wrapper {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.wrapper.normal:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.normal:disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.normal.disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.wrapper.normal:disabled {
            cursor: not-allowed;
}

.wrapper.normal.disabled {
            cursor: not-allowed;
}

/* Enhanced style - when has counter and enhanced */

.wrapper.enhanced {
            cursor: pointer;
}

.wrapper.enhanced:focus {
            outline: none;
}

.wrapper.enhanced .visible-wrapper {
            border-color: var(--notification-enabled-border-color);
            background-color: var(--notification-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--notification-enabled-border-color);
            --base-background-color: var(--notification-enabled-background-color);
}

.wrapper.enhanced.activated .visible-wrapper {
            border-color: var(--notification-activated-border-color);
            background-color: var(--notification-activated-background-color);
            --base-border-color: var(--notification-activated-border-color);
            --base-background-color: var(--notification-activated-background-color);
}

@media (hover:hover) {

.wrapper.enhanced:hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--notification-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--notification-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.wrapper.enhanced:active .visible-wrapper {
            border-color: var(--notification-pressed-border-color);
            background-color: var(--notification-pressed-background-color);
}

.wrapper.enhanced:focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.wrapper.enhanced:disabled .visible-wrapper {
            border-color: var(--notification-disabled-border-color);
            background-color: var(--notification-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-notification-disabled-color) !important;
}

.wrapper.enhanced.disabled .visible-wrapper {
            border-color: var(--notification-disabled-border-color);
            background-color: var(--notification-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-notification-disabled-color) !important;
}

.wrapper.enhanced:disabled {
            cursor: not-allowed;
}

.wrapper.enhanced.disabled {
            cursor: not-allowed;
}

.visible-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  border-radius: var(--ui-components-button-border-radius-top-left)
    var(--ui-components-button-border-radius-top-right)
    var(--ui-components-button-border-radius-bottom-right)
    var(--ui-components-button-border-radius-bottom-left);
}

/* Visible wrapper when no counter (flat) */

.wrapper.flat .visible-wrapper {
  height: var(--ui-components-icon-button-visual-target-size);
  min-width: var(--ui-components-icon-button-visual-target-size);
}

/* Visible wrapper when has counter (normal or enhanced) */

.wrapper.has-counter .visible-wrapper {
  height: var(--app-components-notification-button-visual-target-size);
  min-width: var(--app-components-notification-button-visual-target-size);
  padding: 0 var(--app-components-notification-button-padding-horizontal);
  gap: var(--app-components-notification-button-counter-spacing);
}

/* Visible wrapper when active but no counter (normal or enhanced) */

.wrapper.is-active:not(.has-counter):not(.flat) .visible-wrapper {
  height: var(--app-components-notification-button-visual-target-size);
  min-width: var(--app-components-notification-button-visual-target-size);
  padding: 0 var(--app-components-notification-button-padding-horizontal);
}

/* Enhanced notification background */

.wrapper.enhanced .visible-wrapper {
  border-color: var(--notification-enabled-border-color);
  background: var(--notification-enabled-background-color);
}

.icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--ui-components-icon-button-icon-size);
  height: var(--global-size-spacing-icon-icon-size-regular);
}

obi-notification,
obi-notification-filled {
  width: 100%;
  height: 100%;
  flex-shrink: 0;
}

::slotted([slot="icon"]) {
  width: 100%;
  height: 100%;
  color: inherit;
  flex-shrink: 0;
}

.count-label {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-button-font-weight);
  font-size: var(--global-typography-ui-button-font-size);
  line-height: var(--global-typography-ui-button-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  line-height: 1;
  white-space: nowrap;
}

/* Flat style (no counter) color rules */

.wrapper.flat obi-notification,
.wrapper.flat ::slotted([slot="icon"]) {
  color: var(--on-flat-neutral-color);
}

.wrapper.flat.is-active obi-notification-filled,
.wrapper.flat.is-active ::slotted([slot="icon"]) {
  color: var(--notification-enabled-background-color);
}

/* Normal style (with counter) color rules - always notification color when normal */

.wrapper.normal obi-notification,
.wrapper.normal obi-notification-filled,
.wrapper.normal ::slotted([slot="icon"]) {
  color: var(--notification-enabled-background-color);
}

.wrapper.normal .count-label {
  color: var(--on-normal-active-color);
}

/* Enhanced style (with counter) color rules */

.wrapper.enhanced obi-notification,
.wrapper.enhanced obi-notification-filled,
.wrapper.enhanced ::slotted([slot="icon"]) {
  color: var(--on-notification-active-color);
}

.wrapper.enhanced .count-label {
  color: var(--on-alarm-active-color);
}

@media (prefers-reduced-motion: reduce) {
  .wrapper {
    transition: none;
  }
}
`;var P7=Object.defineProperty;var z7=Object.getOwnPropertyDescriptor;var i0=(e,t,i,o)=>{var r=o>1?void 0:o?z7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)P7(t,i,r);return r};var ql=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.1716 17H20V5H4V17H9.82843L12 19.1716L14.1716 17ZM12 22L9 19H5.2C4.0799 19 3.51984 19 3.09202 18.782C2.71569 18.5903 2.40973 18.2843 2.21799 17.908C2 17.4802 2 16.9201 2 15.8V6.2C2 5.0799 2 4.51984 2.21799 4.09202C2.40973 3.71569 2.71569 3.40973 3.09202 3.21799C3.51984 3 4.07989 3 5.2 3H18.8C19.9201 3 20.4802 3 20.908 3.21799C21.2843 3.40973 21.5903 3.71569 21.782 4.09202C22 4.51984 22 5.08008 22 6.20055V15.7994C22 16.9199 22 17.4802 21.782 17.908C21.5903 18.2843 21.2843 18.5903 20.908 18.782C20.4802 19 19.9201 19 18.8 19H15L12 22Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M14.1716 17H20V5H4V17H9.82843L12 19.1716L14.1716 17ZM12 22L9 19H5.2C4.0799 19 3.51984 19 3.09202 18.782C2.71569 18.5903 2.40973 18.2843 2.21799 17.908C2 17.4802 2 16.9201 2 15.8V6.2C2 5.0799 2 4.51984 2.21799 4.09202C2.40973 3.71569 2.71569 3.40973 3.09202 3.21799C3.51984 3 4.07989 3 5.2 3H18.8C19.9201 3 20.4802 3 20.908 3.21799C21.2843 3.40973 21.5903 3.71569 21.782 4.09202C22 4.51984 22 5.08008 22 6.20055V15.7994C22 16.9199 22 17.4802 21.782 17.908C21.5903 18.2843 21.2843 18.5903 20.908 18.782C20.4802 19 19.9201 19 18.8 19H15L12 22Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ql.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;i0([l({type:Boolean})],ql.prototype,"useCssColor",2);ql=i0([x("obi-notification")],ql);var B7=Object.defineProperty;var O7=Object.getOwnPropertyDescriptor;var a0=(e,t,i,o)=>{var r=o>1?void 0:o?O7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)B7(t,i,r);return r};var Yl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M5 4C3.89543 4 3 4.89543 3 6V16C3 17.1046 3.89543 18 5 18H9L12 21L15 18H19C20.1046 18 21 17.1046 21 16V6C21 4.89543 20.1046 4 19 4H5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M5 4C3.89543 4 3 4.89543 3 6V16C3 17.1046 3.89543 18 5 18H9L12 21L15 18H19C20.1046 18 21 17.1046 21 16V6C21 4.89543 20.1046 4 19 4H5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Yl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;a0([l({type:Boolean})],Yl.prototype,"useCssColor",2);Yl=a0([x("obi-notification-filled")],Yl);var D7=Object.defineProperty;var E7=Object.getOwnPropertyDescriptor;var va=(e,t,i,o)=>{var r=o>1?void 0:o?E7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)D7(t,i,r);return r};var Yo=class extends k{constructor(){super(...arguments);this.buttonStyle="flat";this.count=0;this.showCount=false;this.isActive=false;this.ariaLabel="Notifications"}render(){const e=this.isActive&&this.buttonStyle==="normal";const t=this.isActive&&this.buttonStyle==="enhanced";const i=this.buttonStyle==="flat"||!e&&!t;const o=(e||t)&&this.showCount;const r={wrapper:true,"is-active":this.isActive,"has-counter":o,flat:i,normal:e,enhanced:t};const a={"visible-wrapper":true};return h`
      <button
        class="${J(r)}"
        @click="${this.handleClick}"
        aria-label="${this.ariaLabel}${o?`, ${this.count} new`:""}"
        aria-pressed="${this.isActive}"
        role="button"
        type="button"
      >
        <div class="${J(a)}">
          <div class="icon-container">
            <slot name="icon"> ${this.renderDefaultIcon()} </slot>
          </div>
          ${o?h` <span class="count-label">${this.count}</span> `:w}
        </div>
      </button>
    `}renderDefaultIcon(){if(this.isActive){return h`<obi-notification-filled></obi-notification-filled>`}return h`<obi-notification></obi-notification>`}handleClick(){const e=new CustomEvent("obc-click",{detail:{count:this.count,isActive:!this.isActive},composed:true,bubbles:true});this.dispatchEvent(e)}};Yo.styles=Q(o0);va([l({type:String})],Yo.prototype,"buttonStyle",2);va([l({type:Number})],Yo.prototype,"count",2);va([l({type:Boolean})],Yo.prototype,"showCount",2);va([l({type:Boolean})],Yo.prototype,"isActive",2);va([l({type:String})],Yo.prototype,"ariaLabel",2);Yo=va([x("obc-notification-button")],Yo);var n0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }
obi-notification-filled {
  color: var(--notification-enabled-background-color);
}
`;var l0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
  user-select: none;
}

.wrapper {
  display: flex;
  width: var(--app-components-topbar-message-item-width);
  height: var(--app-components-topbar-message-item-touch-target);
  align-items: center;
}

.wrapper.large {
  height: var(--app-components-topbar-message-item-touch-target-size-tall);
  padding: var(--app-components-topbar-message-item-tall-padding-vertical) 0px;
}

.message-item-touch {
            cursor: pointer;
}

.message-item-touch:focus {
            outline: none;
}

.message-item-touch .message-item {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.message-item-touch.activated .message-item {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

.message-item-touch:hover .message-item {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

.message-item-touch:active .message-item {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

.message-item-touch:focus-visible .message-item {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

.message-item-touch:disabled .message-item {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.message-item-touch.disabled .message-item {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.message-item-touch:disabled {
            cursor: not-allowed;
}

.message-item-touch.disabled {
            cursor: not-allowed;
}

.message-item-touch {
  flex-grow: 1;
  flex-shrink: 1;
  min-width: 0;
  display: flex;
  appearance: none;
  border: none;
  background-color: transparent;
  padding: 0;
}

.large .message-item-touch {
    height: 100%;
  }

.message-item {
  display: flex;
  flex-grow: 1;
  min-width: 0;
  height: var(--app-components-topbar-message-item-visual-target);
  padding: 0px var(--app-components-topbar-message-item-padding-horizontal);
  gap: var(--app-components-topbar-message-item-label-spacing);
  align-items: center;
  border-radius: var(
      --app-components-topbar-message-item-border-radius-top-left
    )
    var(--app-components-topbar-message-item-border-radius-top-right)
    var(--app-components-topbar-message-item-border-radius-bottom-right)
    var(--app-components-topbar-message-item-border-radius-bottom-left);

  /* Support both old action-based and new type-based classes */
}

.action-text-button .message-item,.action-icon-button .message-item,.action-icon-no-click .message-item,.type-with-button .message-item,.type-with-icon-button .message-item {
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
    border-right-width: 0;
  }

.large .message-item {
    height: 100%;
  }

.icon {
  width: var(--app-components-topbar-message-item-icon-size);
  height: var(--app-components-topbar-message-item-icon-size);
  color: var(--element-neutral-color);
}

.content-container {
  display: flex;
  min-width: 0;
  flex-grow: 1;
  flex-shrink: 1;
  flex-basis: 0;
  justify-content: center;
  align-items: center;
  gap: var(--app-components-topbar-message-item-icon-spacing);
}

.message-container {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: var(--app-components-topbar-message-item-label-spacing);
  width: 100%;
}

.message-container.large {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: flex-start;
    flex-grow: 1;
    flex-shrink: 1;
    flex-basis: 0;
    gap: 0;
  }

.title-container {
  min-width: 0;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--app-components-topbar-message-item-label-padding);
}

.large .title-container {
    width: 100%;
  }

.title {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-active-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.description {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  flex-shrink: 10000000;
  color: var(--element-neutral-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  width: 100%;
  text-align: left;
}

::slotted(*) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timestamp-container {
  display: flex;
  align-items: center;
  gap: var(--app-components-topbar-message-item-label-spacing);
  flex-shrink: 0;
}

.time {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
  flex-shrink: 0;
}

.action-wrapper {
  appearance: none;
  border: none;
  background-color: transparent;
  padding: 0;
  display: flex;
  min-width: var(--global-size-spacing-touch-target-min);
  min-height: var(--global-size-spacing-touch-target-min);
  padding: var(--ui-components-icon-button-padding-vertical) 0px;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;

  /* Text button should be 64px wide */
}

.action-wrapper.action-text-button,.type-with-button .action-wrapper {
    width: var(--app-components-topbar-message-item-cta-button-width);
  }

/* Icon button should be 48px wide (touch target) */

.action-wrapper.action-icon-button,.type-with-icon-button .action-wrapper {
    width: var(--global-size-spacing-touch-target-min);
  }

.action-wrapper.action-icon-button,.type-with-icon-button .action-wrapper {
    color: var(--on-normal-neutral-color);
    width: var(--global-size-spacing-touch-target-min);
  }

.action-wrapper.action-text-button,.type-with-button .action-wrapper {
    color: var(--on-normal-active-color);
  }

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper) {
            cursor: pointer;
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):focus {
            outline: none;
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper) .action {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.activated:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper) .action {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):hover .action {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):active .action {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):focus-visible .action {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):disabled .action {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.disabled:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper) .action {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper):disabled {
            cursor: not-allowed;
}

.disabled:is(.action-wrapper.action-icon-button,.action-wrapper.action-text-button,.type-with-button .action-wrapper,.type-with-icon-button .action-wrapper) {
            cursor: not-allowed;
}

:is(.action-icon-no-click .action-wrapper) .action {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.large .action-wrapper {
    height: 100%;
    padding: 0;
  }

.action {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-button-font-weight);
  font-size: var(--global-typography-ui-button-font-size);
  line-height: var(--global-typography-ui-button-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  display: flex;
  height: var(--ui-components-icon-button-visual-target-size);
  width: 100%;
  padding: 0 var(--ui-components-button-padding-horizontal);
  justify-content: center;
  align-items: center;
  align-self: stretch;
  border-radius: 0 var(--ui-components-button-border-radius-top-right)
    var(--ui-components-button-border-radius-bottom-right) 0;
}

.large .action {
    height: 100%;
  }

/* For icon buttons, constrain the icon size */

:is(.action-icon-button .action,.type-with-icon-button .action) ::slotted(*) {
      width: var(--ui-components-icon-button-icon-size);
      height: var(--global-size-spacing-icon-icon-size-regular);
    }

/* Text button specific styling */

.action-text-button .action,
.type-with-button .action {
  padding: 0px var(--ui-components-button-label-spacing);
  width: 100%;
}

/* Make sure text content fills available width */

.action-text-button .action ::slotted(*),
.type-with-button .action ::slotted(*) {
  width: 100%;
  text-align: center;
}

.wrapper.empty {
  justify-content: center;
  flex-direction: column;
}

.empty-message {
  display: flex;
  width: 100%;
  height: var(--app-components-topbar-message-item-visual-target);
  padding: 0px var(--app-components-topbar-message-item-padding-horizontal);
  align-items: center;
  flex-shrink: 0;
  align-self: stretch;
  border-radius: var(
      --app-components-topbar-message-item-border-radius-top-left
    )
    var(--app-components-topbar-message-item-border-radius-top-right)
    var(--app-components-topbar-message-item-border-radius-bottom-right)
    var(--app-components-topbar-message-item-border-radius-bottom-left);
}

.empty-message {
            border-color: var(--indent-enabled-border-color);
            background-color: var(--indent-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            --base-border-color: var(--indent-enabled-border-color);
            --base-background-color: var(--indent-enabled-background-color);
  color: var(--on-indent-neutral-color);
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-body-font-weight);
  font-size: var(--global-typography-ui-body-font-size);
  line-height: var(--global-typography-ui-body-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
}

.large .empty-message {
    height: 100%;
  }
`;var R7=Object.defineProperty;var I7=Object.getOwnPropertyDescriptor;var Qo=(e,t,i,o)=>{var r=o>1?void 0:o?I7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)R7(t,i,r);return r};var Si=(e=>{e["Simple"]="simple";e["WithButton"]="with-button";e["WithIconButton"]="with-icon-button";e["Inactive"]="inactive";return e})(Si||{});var pn=(e=>{e["Regular"]="regular";e["Tall"]="tall";return e})(pn||{});var uo=class extends k{constructor(){super(...arguments);this.type="with-button";this.size="regular";this.showTitle=true;this.showDescription=true;this.showTimestamp=true;this.hasTimestamp2=false;this.hasSecondaryIcon=false}onMessageClick(){this.dispatchEvent(new CustomEvent("message-click"))}onActionClick(){this.dispatchEvent(new CustomEvent("action-click"))}render(){const e=this.type==="inactive";const t=this.size==="tall";return h`
      <div
        class=${J({wrapper:true,empty:e,large:t,[`type-${this.type}`]:true})}
      >
        ${e?h`<div class="empty-message">
              <slot name="empty">No active messages</slot>
            </div>`:h`
              <button class="message-item-touch" @click=${this.onMessageClick}>
                <div class="message-item">
                  <div class="icon primary">
                    <slot name="primary-icon"></slot>
                  </div>
                  <div class="content-container">
                    ${this.hasSecondaryIcon?h`<div class="icon secondary">
                          <slot name="secondary-icon"></slot>
                        </div>`:w}
                    <div class="message-container ${t?"large":""}">
                      <div class="title-container">
                        ${this.showTitle?h`<div class="title">
                              <slot name="title"></slot>
                            </div>`:w}
                        ${t?h`
                              <div class="timestamp-container">
                                ${this.showTimestamp?h`<div class="time">
                                      <slot name="time"></slot>
                                    </div>`:w}
                                ${this.hasTimestamp2?h`<div class="time">
                                      <slot name="time-secondary"></slot>
                                    </div>`:w}
                              </div>
                            `:w}
                      </div>
                      ${this.showDescription?h`<div class="description">
                            <slot name="description"></slot>
                          </div>`:w}
                    </div>
                  </div>
                  ${!t?h`
                        <div class="timestamp-container">
                          ${this.showTimestamp?h`<div class="time">
                                <slot name="time"></slot>
                              </div>`:w}
                          ${this.hasTimestamp2?h`<div class="time secondary">
                                <slot name="time-secondary"></slot>
                              </div>`:w}
                        </div>
                      `:w}
                </div>
              </button>
              ${this.type==="with-button"?h`
                    <button
                      class="action-wrapper action-text-button"
                      @click=${this.onActionClick}
                    >
                      <div class="action">
                        <slot name="action-text"></slot>
                      </div>
                    </button>
                  `:this.type==="with-icon-button"?h`
                      <button
                        class="action-wrapper action-icon-button"
                        @click=${this.onActionClick}
                      >
                        <div class="action">
                          <slot name="action-icon"></slot>
                        </div>
                      </button>
                    `:w}
            `}
      </div>
    `}};uo.styles=Q(l0);Qo([l({type:String})],uo.prototype,"type",2);Qo([l({type:String})],uo.prototype,"size",2);Qo([l({type:Boolean,attribute:false})],uo.prototype,"showTitle",2);Qo([l({type:Boolean,attribute:false})],uo.prototype,"showDescription",2);Qo([l({type:Boolean,attribute:false})],uo.prototype,"showTimestamp",2);Qo([l({type:Boolean})],uo.prototype,"hasTimestamp2",2);Qo([l({type:Boolean})],uo.prototype,"hasSecondaryIcon",2);uo=Qo([x("obc-topbar-message-item")],uo);var N7=Object.defineProperty;var j7=Object.getOwnPropertyDescriptor;var zt=(e,t,i,o)=>{var r=o>1?void 0:o?j7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)N7(t,i,r);return r};var $t=class extends k{constructor(){super(...arguments);this.title="";this.description="";this.time="";this.timeSecondary="";this.actionLabel="View";this.type="simple";this.size="regular";this.showTitle=true;this.showDescription=true;this.showTimestamp=true;this.hasTimestamp2=false;this.hasSecondaryIcon=false;this.large=false;this.empty=false;this.emptyText="No active notification"}get mappedType(){if(this.empty||this.type==="inactive"){return Si.Inactive}switch(this.type){case"with-button":return Si.WithButton;case"with-icon-button":return Si.WithIconButton;case"simple":return Si.Simple;default:return Si.Simple}}get mappedSize(){if(this.large){return pn.Tall}return this.size==="tall"?pn.Tall:pn.Regular}handleMessageClick(){this.dispatchEvent(new CustomEvent("message-click"))}handleActionClick(){this.dispatchEvent(new CustomEvent("action-click"))}render(){return h`
      <obc-topbar-message-item
        .type=${this.mappedType}
        .size=${this.mappedSize}
        .showTitle=${this.showTitle}
        .showDescription=${this.showDescription}
        .showTimestamp=${this.showTimestamp}
        .hasTimestamp2=${this.hasTimestamp2}
        .hasSecondaryIcon=${this.hasSecondaryIcon}
        @message-click=${this.handleMessageClick}
        @action-click=${this.handleActionClick}
      >
        <obi-notification-filled slot="primary-icon"></obi-notification-filled>

        ${this.hasSecondaryIcon?h`<slot name="secondary-icon" slot="secondary-icon"></slot>`:w}
        ${this.title&&this.showTitle?h`<span slot="title">${this.title}</span>`:w}
        ${this.description&&this.showDescription?h`<span slot="description">${this.description}</span>`:w}
        ${this.time&&this.showTimestamp?h`<span slot="time">${this.time}</span>`:w}
        ${this.timeSecondary&&this.hasTimestamp2?h`<span slot="time-secondary">${this.timeSecondary}</span>`:w}
        ${this.type==="with-button"?h`<span slot="action-text">${this.actionLabel}</span>`:this.type==="with-icon-button"?h`<obi-close-google slot="action-icon"></obi-close-google>`:w}

        <span slot="empty">${this.emptyText}</span>
      </obc-topbar-message-item>
    `}};$t.styles=Q(n0);zt([l({type:String})],$t.prototype,"title",2);zt([l({type:String})],$t.prototype,"description",2);zt([l({type:String})],$t.prototype,"time",2);zt([l({type:String})],$t.prototype,"timeSecondary",2);zt([l({type:String})],$t.prototype,"actionLabel",2);zt([l({type:String})],$t.prototype,"type",2);zt([l({type:String})],$t.prototype,"size",2);zt([l({type:Boolean,attribute:false})],$t.prototype,"showTitle",2);zt([l({type:Boolean,attribute:false})],$t.prototype,"showDescription",2);zt([l({type:Boolean,attribute:false})],$t.prototype,"showTimestamp",2);zt([l({type:Boolean})],$t.prototype,"hasTimestamp2",2);zt([l({type:Boolean})],$t.prototype,"hasSecondaryIcon",2);zt([l({type:Boolean})],$t.prototype,"large",2);zt([l({type:Boolean})],$t.prototype,"empty",2);zt([l({type:String})],$t.prototype,"emptyText",2);$t=zt([x("obc-notification-message-item")],$t);var F7=Object.defineProperty;var U7=Object.getOwnPropertyDescriptor;var s0=(e,t,i,o)=>{var r=o>1?void 0:o?U7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)F7(t,i,r);return r};var Ql=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C8.13401 5 5 8.13401 5 12C5 15.866 8.13401 19 12 19C13.933 19 15.683 18.2165 16.9497 16.9497L18.364 18.364C16.7353 19.9926 14.4853 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C14.8273 3 17.35 4.30367 19 6.34267V3H21V10H14V8H17.7453C16.4804 6.18652 14.3787 5 12 5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C8.13401 5 5 8.13401 5 12C5 15.866 8.13401 19 12 19C13.933 19 15.683 18.2165 16.9497 16.9497L18.364 18.364C16.7353 19.9926 14.4853 21 12 21C7.02944 21 3 16.9706 3 12C3 7.02944 7.02944 3 12 3C14.8273 3 17.35 4.30367 19 6.34267V3H21V10H14V8H17.7453C16.4804 6.18652 14.3787 5 12 5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Ql.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;s0([l({type:Boolean})],Ql.prototype,"useCssColor",2);Ql=s0([x("obi-refresh-google")],Ql);var W7=Object.defineProperty;var G7=Object.getOwnPropertyDescriptor;var c0=(e,t,i,o)=>{var r=o>1?void 0:o?G7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)W7(t,i,r);return r};var Kl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M4 19V17H6V10C6 8.61667 6.41667 7.3875 7.25 6.3125C8.08333 5.2375 9.16667 4.53333 10.5 4.2V3.5C10.5 3.08333 10.6458 2.72917 10.9375 2.4375C11.2292 2.14583 11.5833 2 12 2C12.4167 2 12.7708 2.14583 13.0625 2.4375C13.3542 2.72917 13.5 3.08333 13.5 3.5V4.2C14.8333 4.53333 15.9167 5.2375 16.75 6.3125C17.5833 7.3875 18 8.61667 18 10V17H20V19H4ZM12 22C11.45 22 10.9792 21.8042 10.5875 21.4125C10.1958 21.0208 10 20.55 10 20H14C14 20.55 13.8042 21.0208 13.4125 21.4125C13.0208 21.8042 12.55 22 12 22ZM8 17H16V10C16 8.9 15.6083 7.95833 14.825 7.175C14.0417 6.39167 13.1 6 12 6C10.9 6 9.95833 6.39167 9.175 7.175C8.39167 7.95833 8 8.9 8 10V17Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 19V17H6V10C6 8.61667 6.41667 7.3875 7.25 6.3125C8.08333 5.2375 9.16667 4.53333 10.5 4.2V3.5C10.5 3.08333 10.6458 2.72917 10.9375 2.4375C11.2292 2.14583 11.5833 2 12 2C12.4167 2 12.7708 2.14583 13.0625 2.4375C13.3542 2.72917 13.5 3.08333 13.5 3.5V4.2C14.8333 4.53333 15.9167 5.2375 16.75 6.3125C17.5833 7.3875 18 8.61667 18 10V17H20V19H4ZM12 22C11.45 22 10.9792 21.8042 10.5875 21.4125C10.1958 21.0208 10 20.55 10 20H14C14 20.55 13.8042 21.0208 13.4125 21.4125C13.0208 21.8042 12.55 22 12 22ZM8 17H16V10C16 8.9 15.6083 7.95833 14.825 7.175C14.0417 6.39167 13.1 6 12 6C10.9 6 9.95833 6.39167 9.175 7.175C8.39167 7.95833 8 8.9 8 10V17Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Kl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;c0([l({type:Boolean})],Kl.prototype,"useCssColor",2);Kl=c0([x("obi-alerts")],Kl);var q7=Object.defineProperty;var Y7=Object.getOwnPropertyDescriptor;var d0=(e,t,i,o)=>{var r=o>1?void 0:o?Y7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)q7(t,i,r);return r};var Xl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M1.80718 1.3938L0.393188 2.80779L5.5855 8.0001H5.19963C4.07953 8.0001 3.51948 8.0001 3.09165 8.21809C2.71533 8.40983 2.40937 8.71579 2.21762 9.09212C1.99963 9.51994 1.99963 10.08 1.99963 11.2001V12.8001C1.99963 13.9202 1.99963 14.4803 2.21762 14.9081C2.40937 15.2844 2.71533 15.5904 3.09165 15.7821C3.51948 16.0001 4.07953 16.0001 5.19963 16.0001H7.99963L11.2683 19.2687C12.125 20.1255 12.5534 20.5539 12.9212 20.5828C13.2403 20.6079 13.5521 20.4787 13.76 20.2353C13.9996 19.9548 13.9996 19.349 13.9996 18.1374V16.4142L20.1922 22.6068L21.6064 21.1926L13.9996 13.586V5.86284C13.9996 4.65121 13.9996 4.04539 13.76 3.76486C13.5521 3.52145 13.2403 3.39228 12.9212 3.41739C12.5534 3.44634 12.125 3.87472 11.2683 4.73147L8.20663 7.7931L1.80718 1.3938ZM7.5855 10.0001H3.99963C3.99963 10.0001 3.99963 12.438 3.99963 14.0001H8.82806L11.9996 17.1717V14.4142L7.5855 10.0001ZM11.9996 11.586L9.62086 9.2073L11.9996 6.82853V11.586Z" fill="currentColor"/>
<path d="M20.3852 17.1434C20.7544 16.6132 21.0663 16.0436 21.3147 15.444C21.767 14.352 21.9998 13.1817 21.9998 11.9998C21.9998 10.8179 21.767 9.64758 21.3147 8.55565C20.8624 7.46372 20.1995 6.47157 19.3637 5.63584C18.528 4.80011 17.5359 4.13718 16.4439 3.68489C16.2972 3.62413 16.1491 3.56733 15.9998 3.51452V5.67525C16.7228 6.0182 17.3825 6.48298 17.9495 7.05006C18.5995 7.70007 19.1152 8.47174 19.4669 9.32102C19.8187 10.1703 19.9998 11.0805 19.9998 11.9998C19.9998 12.9191 19.8187 13.8293 19.4669 14.6786C19.3198 15.0337 19.1441 15.3753 18.9419 15.7L20.3852 17.1434Z" fill="currentColor"/>
<path d="M17.3801 14.1383L15.9998 12.758V8.5357C16.3019 8.71011 16.5805 8.92366 16.8282 9.17138C17.1996 9.54281 17.4943 9.98377 17.6953 10.4691C17.8963 10.9544 17.9998 11.4745 17.9998 11.9998C17.9998 12.5251 17.8963 13.0452 17.6953 13.5305C17.6076 13.7423 17.5021 13.9456 17.3801 14.1383Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M1.80718 1.3938L0.393188 2.80779L5.5855 8.0001H5.19963C4.07953 8.0001 3.51948 8.0001 3.09165 8.21809C2.71533 8.40983 2.40937 8.71579 2.21762 9.09212C1.99963 9.51994 1.99963 10.08 1.99963 11.2001V12.8001C1.99963 13.9202 1.99963 14.4803 2.21762 14.9081C2.40937 15.2844 2.71533 15.5904 3.09165 15.7821C3.51948 16.0001 4.07953 16.0001 5.19963 16.0001H7.99963L11.2683 19.2687C12.125 20.1255 12.5534 20.5539 12.9212 20.5828C13.2403 20.6079 13.5521 20.4787 13.76 20.2353C13.9996 19.9548 13.9996 19.349 13.9996 18.1374V16.4142L20.1922 22.6068L21.6064 21.1926L13.9996 13.586V5.86284C13.9996 4.65121 13.9996 4.04539 13.76 3.76486C13.5521 3.52145 13.2403 3.39228 12.9212 3.41739C12.5534 3.44634 12.125 3.87472 11.2683 4.73147L8.20663 7.7931L1.80718 1.3938ZM7.5855 10.0001H3.99963C3.99963 10.0001 3.99963 12.438 3.99963 14.0001H8.82806L11.9996 17.1717V14.4142L7.5855 10.0001ZM11.9996 11.586L9.62086 9.2073L11.9996 6.82853V11.586Z" style="fill: var(--element-active-color)"/>
<path d="M20.3852 17.1434C20.7544 16.6132 21.0663 16.0436 21.3147 15.444C21.767 14.352 21.9998 13.1817 21.9998 11.9998C21.9998 10.8179 21.767 9.64758 21.3147 8.55565C20.8624 7.46372 20.1995 6.47157 19.3637 5.63584C18.528 4.80011 17.5359 4.13718 16.4439 3.68489C16.2972 3.62413 16.1491 3.56733 15.9998 3.51452V5.67525C16.7228 6.0182 17.3825 6.48298 17.9495 7.05006C18.5995 7.70007 19.1152 8.47174 19.4669 9.32102C19.8187 10.1703 19.9998 11.0805 19.9998 11.9998C19.9998 12.9191 19.8187 13.8293 19.4669 14.6786C19.3198 15.0337 19.1441 15.3753 18.9419 15.7L20.3852 17.1434Z" style="fill: var(--element-active-color)"/>
<path d="M17.3801 14.1383L15.9998 12.758V8.5357C16.3019 8.71011 16.5805 8.92366 16.8282 9.17138C17.1996 9.54281 17.4943 9.98377 17.6953 10.4691C17.8963 10.9544 17.9998 11.4745 17.9998 11.9998C17.9998 12.5251 17.8963 13.0452 17.6953 13.5305C17.6076 13.7423 17.5021 13.9456 17.3801 14.1383Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Xl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;d0([l({type:Boolean})],Xl.prototype,"useCssColor",2);Xl=d0([x("obi-sound-muted")],Xl);var Q7=Object.defineProperty;var K7=Object.getOwnPropertyDescriptor;var p0=(e,t,i,o)=>{var r=o>1?void 0:o?K7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Q7(t,i,r);return r};var Jl=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M10 12C8.9 12 7.95833 11.6083 7.175 10.825C6.39167 10.0417 6 9.1 6 8C6 6.9 6.39167 5.95833 7.175 5.175C7.95833 4.39167 8.9 4 10 4C11.1 4 12.0417 4.39167 12.825 5.175C13.6083 5.95833 14 6.9 14 8C14 9.1 13.6083 10.0417 12.825 10.825C12.0417 11.6083 11.1 12 10 12ZM2 20V17.2C2 16.65 2.14167 16.1333 2.425 15.65C2.70833 15.1667 3.1 14.8 3.6 14.55C4.45 14.1167 5.40833 13.75 6.475 13.45C7.54167 13.15 8.71667 13 10 13H10.35C10.45 13 10.55 13.0167 10.65 13.05C10.5167 13.35 10.4042 13.6625 10.3125 13.9875C10.2208 14.3125 10.15 14.65 10.1 15H10C8.81667 15 7.75417 15.15 6.8125 15.45C5.87083 15.75 5.1 16.05 4.5 16.35C4.35 16.4333 4.22917 16.55 4.1375 16.7C4.04583 16.85 4 17.0167 4 17.2V18H10.3C10.4 18.35 10.5333 18.6958 10.7 19.0375C10.8667 19.3792 11.05 19.7 11.25 20H2ZM16 21L15.7 19.5C15.5 19.4167 15.3125 19.3292 15.1375 19.2375C14.9625 19.1458 14.7833 19.0333 14.6 18.9L13.15 19.35L12.15 17.65L13.3 16.65C13.2667 16.4167 13.25 16.2 13.25 16C13.25 15.8 13.2667 15.5833 13.3 15.35L12.15 14.35L13.15 12.65L14.6 13.1C14.7833 12.9667 14.9625 12.8542 15.1375 12.7625C15.3125 12.6708 15.5 12.5833 15.7 12.5L16 11H18L18.3 12.5C18.5 12.5833 18.6875 12.675 18.8625 12.775C19.0375 12.875 19.2167 13 19.4 13.15L20.85 12.65L21.85 14.4L20.7 15.4C20.7333 15.6 20.75 15.8083 20.75 16.025C20.75 16.2417 20.7333 16.45 20.7 16.65L21.85 17.65L20.85 19.35L19.4 18.9C19.2167 19.0333 19.0375 19.1458 18.8625 19.2375C18.6875 19.3292 18.5 19.4167 18.3 19.5L18 21H16ZM17 18C17.55 18 18.0208 17.8042 18.4125 17.4125C18.8042 17.0208 19 16.55 19 16C19 15.45 18.8042 14.9792 18.4125 14.5875C18.0208 14.1958 17.55 14 17 14C16.45 14 15.9792 14.1958 15.5875 14.5875C15.1958 14.9792 15 15.45 15 16C15 16.55 15.1958 17.0208 15.5875 17.4125C15.9792 17.8042 16.45 18 17 18ZM10 10C10.55 10 11.0208 9.80417 11.4125 9.4125C11.8042 9.02083 12 8.55 12 8C12 7.45 11.8042 6.97917 11.4125 6.5875C11.0208 6.19583 10.55 6 10 6C9.45 6 8.97917 6.19583 8.5875 6.5875C8.19583 6.97917 8 7.45 8 8C8 8.55 8.19583 9.02083 8.5875 9.4125C8.97917 9.80417 9.45 10 10 10Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 12C8.9 12 7.95833 11.6083 7.175 10.825C6.39167 10.0417 6 9.1 6 8C6 6.9 6.39167 5.95833 7.175 5.175C7.95833 4.39167 8.9 4 10 4C11.1 4 12.0417 4.39167 12.825 5.175C13.6083 5.95833 14 6.9 14 8C14 9.1 13.6083 10.0417 12.825 10.825C12.0417 11.6083 11.1 12 10 12ZM2 20V17.2C2 16.65 2.14167 16.1333 2.425 15.65C2.70833 15.1667 3.1 14.8 3.6 14.55C4.45 14.1167 5.40833 13.75 6.475 13.45C7.54167 13.15 8.71667 13 10 13H10.35C10.45 13 10.55 13.0167 10.65 13.05C10.5167 13.35 10.4042 13.6625 10.3125 13.9875C10.2208 14.3125 10.15 14.65 10.1 15H10C8.81667 15 7.75417 15.15 6.8125 15.45C5.87083 15.75 5.1 16.05 4.5 16.35C4.35 16.4333 4.22917 16.55 4.1375 16.7C4.04583 16.85 4 17.0167 4 17.2V18H10.3C10.4 18.35 10.5333 18.6958 10.7 19.0375C10.8667 19.3792 11.05 19.7 11.25 20H2ZM16 21L15.7 19.5C15.5 19.4167 15.3125 19.3292 15.1375 19.2375C14.9625 19.1458 14.7833 19.0333 14.6 18.9L13.15 19.35L12.15 17.65L13.3 16.65C13.2667 16.4167 13.25 16.2 13.25 16C13.25 15.8 13.2667 15.5833 13.3 15.35L12.15 14.35L13.15 12.65L14.6 13.1C14.7833 12.9667 14.9625 12.8542 15.1375 12.7625C15.3125 12.6708 15.5 12.5833 15.7 12.5L16 11H18L18.3 12.5C18.5 12.5833 18.6875 12.675 18.8625 12.775C19.0375 12.875 19.2167 13 19.4 13.15L20.85 12.65L21.85 14.4L20.7 15.4C20.7333 15.6 20.75 15.8083 20.75 16.025C20.75 16.2417 20.7333 16.45 20.7 16.65L21.85 17.65L20.85 19.35L19.4 18.9C19.2167 19.0333 19.0375 19.1458 18.8625 19.2375C18.6875 19.3292 18.5 19.4167 18.3 19.5L18 21H16ZM17 18C17.55 18 18.0208 17.8042 18.4125 17.4125C18.8042 17.0208 19 16.55 19 16C19 15.45 18.8042 14.9792 18.4125 14.5875C18.0208 14.1958 17.55 14 17 14C16.45 14 15.9792 14.1958 15.5875 14.5875C15.1958 14.9792 15 15.45 15 16C15 16.55 15.1958 17.0208 15.5875 17.4125C15.9792 17.8042 16.45 18 17 18ZM10 10C10.55 10 11.0208 9.80417 11.4125 9.4125C11.8042 9.02083 12 8.55 12 8C12 7.45 11.8042 6.97917 11.4125 6.5875C11.0208 6.19583 10.55 6 10 6C9.45 6 8.97917 6.19583 8.5875 6.5875C8.19583 6.97917 8 7.45 8 8C8 8.55 8.19583 9.02083 8.5875 9.4125C8.97917 9.80417 9.45 10 10 10Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};Jl.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;p0([l({type:Boolean})],Jl.prototype,"useCssColor",2);Jl=p0([x("obi-settings-user-proposal")],Jl);var X7=Object.defineProperty;var J7=Object.getOwnPropertyDescriptor;var h0=(e,t,i,o)=>{var r=o>1?void 0:o?J7(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)X7(t,i,r);return r};var es=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 13L16 17H13V22H11V17H8L12 13Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 11.5607L15.5303 8.03033L14.4697 6.96967L12 9.43934L9.53033 6.96967L8.46967 8.03033L12 11.5607Z" fill="currentColor"/>
<path d="M13 5.5C13 6.05228 12.5523 6.5 12 6.5C11.4477 6.5 11 6.05228 11 5.5C11 4.94772 11.4477 4.5 12 4.5C12.5523 4.5 13 4.94772 13 5.5Z" fill="currentColor"/>
<path d="M13 2C13 2.55228 12.5523 3 12 3C11.4477 3 11 2.55228 11 2C11 1.44772 11.4477 1 12 1C12.5523 1 13 1.44772 13 2Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 13L16 17H13V22H11V17H8L12 13Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 11.5607L15.5303 8.03033L14.4697 6.96967L12 9.43934L9.53033 6.96967L8.46967 8.03033L12 11.5607Z" style="fill: var(--element-active-color)"/>
<path d="M13 5.5C13 6.05228 12.5523 6.5 12 6.5C11.4477 6.5 11 6.05228 11 5.5C11 4.94772 11.4477 4.5 12 4.5C12.5523 4.5 13 4.94772 13 5.5Z" style="fill: var(--element-active-color)"/>
<path d="M13 2C13 2.55228 12.5523 3 12 3C11.4477 3 11 2.55228 11 2C11 1.44772 11.4477 1 12 1C12.5523 1 13 1.44772 13 2Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};es.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;h0([l({type:Boolean})],es.prototype,"useCssColor",2);es=h0([x("obi-collision-avoidance-head-on")],es);var e8=Object.defineProperty;var t8=Object.getOwnPropertyDescriptor;var u0=(e,t,i,o)=>{var r=o>1?void 0:o?t8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)e8(t,i,r);return r};var ts=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M8 19.5V4.5L20 12L8 19.5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M8 19.5V4.5L20 12L8 19.5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ts.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;u0([l({type:Boolean})],ts.prototype,"useCssColor",2);ts=u0([x("obi-media-play")],ts);var r8=Object.defineProperty;var o8=Object.getOwnPropertyDescriptor;var f0=(e,t,i,o)=>{var r=o>1?void 0:o?o8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)r8(t,i,r);return r};var rs=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M10 5H6V19H10V5Z" fill="currentColor"/>
<path d="M18 5H13.9967V19H18V5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M10 5H6V19H10V5Z" style="fill: var(--element-active-color)"/>
<path d="M18 5H13.9967V19H18V5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};rs.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;f0([l({type:Boolean})],rs.prototype,"useCssColor",2);rs=f0([x("obi-media-pause")],rs);var i8=Object.defineProperty;var a8=Object.getOwnPropertyDescriptor;var v0=(e,t,i,o)=>{var r=o>1?void 0:o?a8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)i8(t,i,r);return r};var os=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M17 5V19H20V5H17Z" fill="currentColor"/>
<path d="M4 5V19L15 12L4 5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M17 5V19H20V5H17Z" style="fill: var(--element-active-color)"/>
<path d="M4 5V19L15 12L4 5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};os.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;v0([l({type:Boolean})],os.prototype,"useCssColor",2);os=v0([x("obi-media-skip-next")],os);var n8=Object.defineProperty;var l8=Object.getOwnPropertyDescriptor;var m0=(e,t,i,o)=>{var r=o>1?void 0:o?l8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)n8(t,i,r);return r};var is=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C15.866 5 19 8.13401 19 12C19 15.866 15.866 19 12 19C10.067 19 8.317 18.2165 7.05025 16.9497L5.63604 18.364C7.26472 19.9926 9.51472 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C9.17273 3 6.64996 4.30367 5 6.34267V3H3V10H10V8H6.25469C7.51964 6.18652 9.62125 5 12 5Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 5C15.866 5 19 8.13401 19 12C19 15.866 15.866 19 12 19C10.067 19 8.317 18.2165 7.05025 16.9497L5.63604 18.364C7.26472 19.9926 9.51472 21 12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C9.17273 3 6.64996 4.30367 5 6.34267V3H3V10H10V8H6.25469C7.51964 6.18652 9.62125 5 12 5Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};is.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;m0([l({type:Boolean})],is.prototype,"useCssColor",2);is=m0([x("obi-reset")],is);var s8=Object.defineProperty;var c8=Object.getOwnPropertyDescriptor;var g0=(e,t,i,o)=>{var r=o>1?void 0:o?c8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)s8(t,i,r);return r};var as=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M5 19V5V16.35V14.225V19ZM5 21C4.45 21 3.97917 20.8042 3.5875 20.4125C3.19583 20.0208 3 19.55 3 19V5C3 4.45 3.19583 3.97917 3.5875 3.5875C3.97917 3.19583 4.45 3 5 3H19C19.55 3 20.0208 3.19583 20.4125 3.5875C20.8042 3.97917 21 4.45 21 5V13H19V5H5V19H12V21H5ZM17.35 22L13.8 18.45L15.225 17.05L17.35 19.175L21.6 14.925L23 16.35L17.35 22ZM8 13C8.28333 13 8.52083 12.9042 8.7125 12.7125C8.90417 12.5208 9 12.2833 9 12C9 11.7167 8.90417 11.4792 8.7125 11.2875C8.52083 11.0958 8.28333 11 8 11C7.71667 11 7.47917 11.0958 7.2875 11.2875C7.09583 11.4792 7 11.7167 7 12C7 12.2833 7.09583 12.5208 7.2875 12.7125C7.47917 12.9042 7.71667 13 8 13ZM8 9C8.28333 9 8.52083 8.90417 8.7125 8.7125C8.90417 8.52083 9 8.28333 9 8C9 7.71667 8.90417 7.47917 8.7125 7.2875C8.52083 7.09583 8.28333 7 8 7C7.71667 7 7.47917 7.09583 7.2875 7.2875C7.09583 7.47917 7 7.71667 7 8C7 8.28333 7.09583 8.52083 7.2875 8.7125C7.47917 8.90417 7.71667 9 8 9ZM11 13H17V11H11V13ZM11 9H17V7H11V9Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M5 19V5V16.35V14.225V19ZM5 21C4.45 21 3.97917 20.8042 3.5875 20.4125C3.19583 20.0208 3 19.55 3 19V5C3 4.45 3.19583 3.97917 3.5875 3.5875C3.97917 3.19583 4.45 3 5 3H19C19.55 3 20.0208 3.19583 20.4125 3.5875C20.8042 3.97917 21 4.45 21 5V13H19V5H5V19H12V21H5ZM17.35 22L13.8 18.45L15.225 17.05L17.35 19.175L21.6 14.925L23 16.35L17.35 22ZM8 13C8.28333 13 8.52083 12.9042 8.7125 12.7125C8.90417 12.5208 9 12.2833 9 12C9 11.7167 8.90417 11.4792 8.7125 11.2875C8.52083 11.0958 8.28333 11 8 11C7.71667 11 7.47917 11.0958 7.2875 11.2875C7.09583 11.4792 7 11.7167 7 12C7 12.2833 7.09583 12.5208 7.2875 12.7125C7.47917 12.9042 7.71667 13 8 13ZM8 9C8.28333 9 8.52083 8.90417 8.7125 8.7125C8.90417 8.52083 9 8.28333 9 8C9 7.71667 8.90417 7.47917 8.7125 7.2875C8.52083 7.09583 8.28333 7 8 7C7.71667 7 7.47917 7.09583 7.2875 7.2875C7.09583 7.47917 7 7.71667 7 8C7 8.28333 7.09583 8.52083 7.2875 8.7125C7.47917 8.90417 7.71667 9 8 9ZM11 13H17V11H11V13ZM11 9H17V7H11V9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};as.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;g0([l({type:Boolean})],as.prototype,"useCssColor",2);as=g0([x("obi-list-alt-check-google")],as);var d8=Object.defineProperty;var p8=Object.getOwnPropertyDescriptor;var b0=(e,t,i,o)=>{var r=o>1?void 0:o?p8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)d8(t,i,r);return r};var ns=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" fill="currentColor"/>
<path d="M15.0623 7.5L12.0311 4.5L9 7.5H11.0311V10.5H13.0311V7.5H15.0623Z" fill="currentColor"/>
<path d="M16 8.93782L13 11.9689L16 15V12.9689H19V10.9689H16V8.93782Z" fill="currentColor"/>
<path d="M8 15.0622L11 12.0311L8 9V11.0311H5V13.0311H8V15.0622Z" fill="currentColor"/>
<path d="M9.00012 16.5L12.0312 19.5L15.0623 16.5H13.0312V13.5H11.0312V16.5H9.00012Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 20C16.4183 20 20 16.4183 20 12C20 7.58172 16.4183 4 12 4C7.58172 4 4 7.58172 4 12C4 16.4183 7.58172 20 12 20ZM12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" style="fill: var(--element-active-color)"/>
<path d="M15.0623 7.5L12.0311 4.5L9 7.5H11.0311V10.5H13.0311V7.5H15.0623Z" style="fill: var(--element-active-color)"/>
<path d="M16 8.93782L13 11.9689L16 15V12.9689H19V10.9689H16V8.93782Z" style="fill: var(--element-active-color)"/>
<path d="M8 15.0622L11 12.0311L8 9V11.0311H5V13.0311H8V15.0622Z" style="fill: var(--element-active-color)"/>
<path d="M9.00012 16.5L12.0312 19.5L15.0623 16.5H13.0312V13.5H11.0312V16.5H9.00012Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ns.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;b0([l({type:Boolean})],ns.prototype,"useCssColor",2);ns=b0([x("obi-router-component")],ns);var h8=Object.defineProperty;var u8=Object.getOwnPropertyDescriptor;var y0=(e,t,i,o)=>{var r=o>1?void 0:o?u8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)h8(t,i,r);return r};var ls=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M15.8506 12.4062C17.4207 10.8362 19.6451 10.3174 21.6465 10.8516L21.6475 10.8525C22.182 12.8542 21.6641 15.079 20.0938 16.6494L14.5254 22.2178L10.2822 17.9746L15.8506 12.4062ZM19.8428 12.6562C18.9025 12.7148 17.9811 13.1039 17.2646 13.8203L13.1104 17.9746L14.5244 19.3887L18.6787 15.2354C19.3954 14.5187 19.7844 13.5968 19.8428 12.6562ZM9 14H7V10H9V14ZM6 9H2V7H6V9ZM14 9H10V7H14V9ZM9 2V6H7V2H9Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M15.8506 12.4062C17.4207 10.8362 19.6451 10.3174 21.6465 10.8516L21.6475 10.8525C22.182 12.8542 21.6641 15.079 20.0938 16.6494L14.5254 22.2178L10.2822 17.9746L15.8506 12.4062ZM19.8428 12.6562C18.9025 12.7148 17.9811 13.1039 17.2646 13.8203L13.1104 17.9746L14.5244 19.3887L18.6787 15.2354C19.3954 14.5187 19.7844 13.5968 19.8428 12.6562ZM9 14H7V10H9V14ZM6 9H2V7H6V9ZM14 9H10V7H14V9ZM9 2V6H7V2H9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ls.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;y0([l({type:Boolean})],ls.prototype,"useCssColor",2);ls=y0([x("obi-center-off-iec")],ls);var f8=Object.defineProperty;var v8=Object.getOwnPropertyDescriptor;var w0=(e,t,i,o)=>{var r=o>1?void 0:o?v8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)f8(t,i,r);return r};var ss=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M10.2036 5.55373C11.774 3.98336 13.9983 3.46545 16 4C16.5346 6.0017 16.0166 8.226 14.4463 9.79637L7.93843 16.3042L3.69579 12.0616L10.2036 5.55373ZM11.2643 6.61439C12.2058 5.67289 13.4612 5.23456 14.6969 5.30313C14.7654 6.53876 14.3271 7.79421 13.3856 8.73571L7.93843 14.1829L5.81711 12.0616L11.2643 6.61439Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9564 16.9999C20.6132 16.9999 21.9564 15.6568 21.9564 13.9999C21.9564 12.343 20.6132 10.9999 18.9564 10.9999C17.2995 10.9999 15.9564 12.343 15.9564 13.9999C15.9564 15.6568 17.2995 16.9999 18.9564 16.9999Z" fill="currentColor"/>
<path d="M14.2736 20.0002L15.6878 18.586L14.2736 17.1717L12.8594 18.586L11.4452 17.1717L10.7381 22.1215L15.6878 21.4144L14.2736 20.0002Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path fill-rule="evenodd" clip-rule="evenodd" d="M10.2036 5.55373C11.774 3.98336 13.9983 3.46545 16 4C16.5346 6.0017 16.0166 8.226 14.4463 9.79637L7.93843 16.3042L3.69579 12.0616L10.2036 5.55373ZM11.2643 6.61439C12.2058 5.67289 13.4612 5.23456 14.6969 5.30313C14.7654 6.53876 14.3271 7.79421 13.3856 8.73571L7.93843 14.1829L5.81711 12.0616L11.2643 6.61439Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M18.9564 16.9999C20.6132 16.9999 21.9564 15.6568 21.9564 13.9999C21.9564 12.343 20.6132 10.9999 18.9564 10.9999C17.2995 10.9999 15.9564 12.343 15.9564 13.9999C15.9564 15.6568 17.2995 16.9999 18.9564 16.9999Z" style="fill: var(--element-active-color)"/>
<path d="M14.2736 20.0002L15.6878 18.586L14.2736 17.1717L12.8594 18.586L11.4452 17.1717L10.7381 22.1215L15.6878 21.4144L14.2736 20.0002Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ss.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;w0([l({type:Boolean})],ss.prototype,"useCssColor",2);ss=w0([x("obi-motion-relative-proposal")],ss);var m8=Object.defineProperty;var g8=Object.getOwnPropertyDescriptor;var C0=(e,t,i,o)=>{var r=o>1?void 0:o?g8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)m8(t,i,r);return r};var cs=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M6.66517 5.99945C5.44261 7.222 4.79212 8.78595 4.6814 10.3822H1.35974L5.51182 14.5343L9.66389 10.3822L6.32378 10.3822C6.42988 9.20577 6.91891 8.05242 7.81852 7.1528C9.45628 5.51504 11.906 5.19671 13.8621 6.18398L14.591 4.73537C12.0213 3.439 8.81041 3.85421 6.66517 5.99945Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M8.82261 14.5019C10.1312 13.1934 11.9847 12.7618 13.6528 13.2073C14.0982 14.8754 13.6667 16.7289 12.3581 18.0375L7.64234 22.7533L4.10681 19.2177L8.82261 14.5019ZM12.3225 14.5376C11.4371 14.5464 10.5568 14.889 9.88327 15.5626L6.22813 19.2177L7.64234 20.6319L11.2975 16.9768C11.9711 16.3032 12.3137 15.4229 12.3225 14.5376Z" fill="currentColor"/>
<path d="M22.8451 4.01494C21.1771 3.56944 19.3236 4.00097 18.015 5.30955L13.2992 10.0253L16.8347 13.5609L21.5505 8.84508C22.8591 7.53651 23.2906 5.68299 22.8451 4.01494Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M6.66517 5.99945C5.44261 7.222 4.79212 8.78595 4.6814 10.3822H1.35974L5.51182 14.5343L9.66389 10.3822L6.32378 10.3822C6.42988 9.20577 6.91891 8.05242 7.81852 7.1528C9.45628 5.51504 11.906 5.19671 13.8621 6.18398L14.591 4.73537C12.0213 3.439 8.81041 3.85421 6.66517 5.99945Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M8.82261 14.5019C10.1312 13.1934 11.9847 12.7618 13.6528 13.2073C14.0982 14.8754 13.6667 16.7289 12.3581 18.0375L7.64234 22.7533L4.10681 19.2177L8.82261 14.5019ZM12.3225 14.5376C11.4371 14.5464 10.5568 14.889 9.88327 15.5626L6.22813 19.2177L7.64234 20.6319L11.2975 16.9768C11.9711 16.3032 12.3137 15.4229 12.3225 14.5376Z" style="fill: var(--element-active-color)"/>
<path d="M22.8451 4.01494C21.1771 3.56944 19.3236 4.00097 18.015 5.30955L13.2992 10.0253L16.8347 13.5609L21.5505 8.84508C22.8591 7.53651 23.2906 5.68299 22.8451 4.01494Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};cs.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;C0([l({type:Boolean})],cs.prototype,"useCssColor",2);cs=C0([x("obi-motion-tm-reset-proposal-2")],cs);var b8=Object.defineProperty;var y8=Object.getOwnPropertyDescriptor;var k0=(e,t,i,o)=>{var r=o>1?void 0:o?y8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)b8(t,i,r);return r};var ds=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21.05L3 14.05L4.65 12.8L12 18.5L19.35 12.8L21 14.05L12 21.05ZM12 16L3 9L12 2L21 9L12 16ZM12 13.45L17.75 9L12 4.55L6.25 9L12 13.45Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M12 21.05L3 14.05L4.65 12.8L12 18.5L19.35 12.8L21 14.05L12 21.05ZM12 16L3 9L12 2L21 9L12 16ZM12 13.45L17.75 9L12 4.55L6.25 9L12 13.45Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ds.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;k0([l({type:Boolean})],ds.prototype,"useCssColor",2);ds=k0([x("obi-chart-layers")],ds);var w8=Object.defineProperty;var C8=Object.getOwnPropertyDescriptor;var L0=(e,t,i,o)=>{var r=o>1?void 0:o?C8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)w8(t,i,r);return r};var ps=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M4 8V4H8V2H4C2.89543 2 2 2.89543 2 4V8H4Z" fill="currentColor"/>
<path d="M4 16H2V20C2 21.1046 2.89543 22 4 22H8V20H4V16Z" fill="currentColor"/>
<path d="M16 20V22H20C21.1046 22 22 21.1046 22 20V16H20V20H16Z" fill="currentColor"/>
<path d="M20 8H22V4.00002C22 2.89546 21.1046 2.00003 20 2.00002L16 2V4H20V8Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 8V4H8V2H4C2.89543 2 2 2.89543 2 4V8H4Z" style="fill: var(--element-active-color)"/>
<path d="M4 16H2V20C2 21.1046 2.89543 22 4 22H8V20H4V16Z" style="fill: var(--element-active-color)"/>
<path d="M16 20V22H20C21.1046 22 22 21.1046 22 20V16H20V20H16Z" style="fill: var(--element-active-color)"/>
<path d="M20 8H22V4.00002C22 2.89546 21.1046 2.00003 20 2.00002L16 2V4H20V8Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};ps.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;L0([l({type:Boolean})],ps.prototype,"useCssColor",2);ps=L0([x("obi-target-select-iec")],ps);var k8=Object.defineProperty;var L8=Object.getOwnPropertyDescriptor;var x0=(e,t,i,o)=>{var r=o>1?void 0:o?L8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)k8(t,i,r);return r};var hs=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
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
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};hs.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;x0([l({type:Boolean})],hs.prototype,"useCssColor",2);hs=x0([x("obi-radar-electronic-range-and-bearing-proposal")],hs);var x8=Object.defineProperty;var $8=Object.getOwnPropertyDescriptor;var $0=(e,t,i,o)=>{var r=o>1?void 0:o?$8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)x8(t,i,r);return r};var us=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<path d="M9.6645 14C9.13165 14 8.86523 14 8.72839 14.1092C8.60938 14.2042 8.54015 14.3483 8.54031 14.5005C8.5405 14.6756 8.70694 14.8837 9.03981 15.2998L12 19L14.9602 15.2998C15.2931 14.8837 15.4595 14.6756 15.4597 14.5005C15.4599 14.3483 15.3906 14.2042 15.2716 14.1092C15.1348 14 14.8684 14 14.3355 14H9.6645Z" fill="currentColor"/>
<path d="M2 22H5V20H2V22Z" fill="currentColor"/>
<path d="M7 22H11V20H7V22Z" fill="currentColor"/>
<path d="M13 22H17V20H13V22Z" fill="currentColor"/>
<path d="M19 22H22V20H19V22Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.97034 6.60754C6.8857 6.72976 6.84338 6.79087 6.82134 6.88005C6.80444 6.94847 6.80444 7.05153 6.82134 7.11995C6.84338 7.20913 6.8857 7.27024 6.97034 7.39246C8.05424 8.95767 9.89402 10 12 10C14.106 10 15.9458 8.95766 17.0297 7.39246C17.1143 7.27024 17.1566 7.20913 17.1787 7.11995C17.1956 7.05153 17.1956 6.94847 17.1787 6.88004C17.1566 6.79086 17.1143 6.72975 17.0297 6.60753C15.9458 5.04233 14.106 4 12 4C9.89402 4 8.05424 5.04233 6.97034 6.60754ZM19.3733 7.29651C19.4182 7.19726 19.4406 7.14764 19.4514 7.08452C19.4601 7.03407 19.4601 6.96593 19.4514 6.91548C19.4406 6.85236 19.4182 6.80274 19.3733 6.70349C18.1212 3.93428 15.2928 2 12 2C8.70721 2 5.87877 3.93428 4.62672 6.70349C4.58185 6.80274 4.55941 6.85236 4.54859 6.91548C4.53993 6.96593 4.53993 7.03407 4.54859 7.08452C4.55941 7.14764 4.58185 7.19726 4.62672 7.29651C5.87877 10.0657 8.70721 12 12 12C15.2928 12 18.1212 10.0657 19.3733 7.29651Z" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 9C10.896 9 10 8.104 10 7C10 5.896 10.896 5 12 5C13.104 5 14 5.896 14 7C14 8.104 13.104 9 12 9Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M9.6645 14C9.13165 14 8.86523 14 8.72839 14.1092C8.60938 14.2042 8.54015 14.3483 8.54031 14.5005C8.5405 14.6756 8.70694 14.8837 9.03981 15.2998L12 19L14.9602 15.2998C15.2931 14.8837 15.4595 14.6756 15.4597 14.5005C15.4599 14.3483 15.3906 14.2042 15.2716 14.1092C15.1348 14 14.8684 14 14.3355 14H9.6645Z" style="fill: var(--element-active-color)"/>
<path d="M2 22H5V20H2V22Z" style="fill: var(--element-active-color)"/>
<path d="M7 22H11V20H7V22Z" style="fill: var(--element-active-color)"/>
<path d="M13 22H17V20H13V22Z" style="fill: var(--element-active-color)"/>
<path d="M19 22H22V20H19V22Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M6.97034 6.60754C6.8857 6.72976 6.84338 6.79087 6.82134 6.88005C6.80444 6.94847 6.80444 7.05153 6.82134 7.11995C6.84338 7.20913 6.8857 7.27024 6.97034 7.39246C8.05424 8.95767 9.89402 10 12 10C14.106 10 15.9458 8.95766 17.0297 7.39246C17.1143 7.27024 17.1566 7.20913 17.1787 7.11995C17.1956 7.05153 17.1956 6.94847 17.1787 6.88004C17.1566 6.79086 17.1143 6.72975 17.0297 6.60753C15.9458 5.04233 14.106 4 12 4C9.89402 4 8.05424 5.04233 6.97034 6.60754ZM19.3733 7.29651C19.4182 7.19726 19.4406 7.14764 19.4514 7.08452C19.4601 7.03407 19.4601 6.96593 19.4514 6.91548C19.4406 6.85236 19.4182 6.80274 19.3733 6.70349C18.1212 3.93428 15.2928 2 12 2C8.70721 2 5.87877 3.93428 4.62672 6.70349C4.58185 6.80274 4.55941 6.85236 4.54859 6.91548C4.53993 6.96593 4.53993 7.03407 4.54859 7.08452C4.55941 7.14764 4.58185 7.19726 4.62672 7.29651C5.87877 10.0657 8.70721 12 12 12C15.2928 12 18.1212 10.0657 19.3733 7.29651Z" style="fill: var(--element-active-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M12 9C10.896 9 10 8.104 10 7C10 5.896 10.896 5 12 5C13.104 5 14 5.896 14 7C14 8.104 13.104 9 12 9Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};us.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;$0([l({type:Boolean})],us.prototype,"useCssColor",2);us=$0([x("obi-monitoring-route")],us);var M8=Object.defineProperty;var H8=Object.getOwnPropertyDescriptor;var M0=(e,t,i,o)=>{var r=o>1?void 0:o?H8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)M8(t,i,r);return r};var fs=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="10" fill="currentColor"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" fill="currentColor"/>
<path d="M7.03865 16.2869L11.4846 5.33535C11.6661 4.88821 12.3339 4.88822 12.5154 5.33536L16.9613 16.2869C17.1482 16.7473 16.6205 17.1744 16.1697 16.9277L12.2763 14.7964C12.1053 14.7029 11.8947 14.7029 11.7237 14.7964L7.8303 16.9277C7.37952 17.1744 6.85176 16.7473 7.03865 16.2869Z" fill="currentColor"/>
</svg>
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
<circle cx="12" cy="12" r="10" style="fill: var(--element-active-inverted-color)"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C17.5228 2 22 6.47715 22 12ZM20 12C20 16.4183 16.4183 20 12 20C7.58172 20 4 16.4183 4 12C4 7.58172 7.58172 4 12 4C16.4183 4 20 7.58172 20 12Z" style="fill: var(--element-active-color)"/>
<path d="M7.03865 16.2869L11.4846 5.33535C11.6661 4.88821 12.3339 4.88822 12.5154 5.33536L16.9613 16.2869C17.1482 16.7473 16.6205 17.1744 16.1697 16.9277L12.2763 14.7964C12.1053 14.7029 11.8947 14.7029 11.7237 14.7964L7.8303 16.9277C7.37952 17.1744 6.85176 16.7473 7.03865 16.2869Z" style="fill: var(--element-active-color)"/>
</svg>
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};fs.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;M0([l({type:Boolean})],fs.prototype,"useCssColor",2);fs=M0([x("obi-own-ship-alternative-filled")],fs);var S8=Object.defineProperty;var _8=Object.getOwnPropertyDescriptor;var H0=(e,t,i,o)=>{var r=o>1?void 0:o?_8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)S8(t,i,r);return r};var vs=class extends k{constructor(){super(...arguments);this.useCssColor=false;this.icon=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
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
`;this.iconCss=c`<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
`}render(){return h`
      <div class="wrapper">${this.useCssColor?this.iconCss:this.icon}</div>
    `}};vs.styles=L`
    .wrapper {
      height: 100%;
      width: 100%;
      line-height: 0;
    }
    .wrapper > * {
      height: 100%;
      width: 100%;
    }
  `;H0([l({type:Boolean})],vs.prototype,"useCssColor",2);vs=H0([x("obi-vessel-type-cargo-filled")],vs);var S0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  display: block;
  width: fit-content;
}

.wrapper {
  display: flex;
  flex-direction: column;
  width: fit-content;
  padding: var(--instrument-components-readout-padding-vertical)
    var(--instrument-components-readout-padding-horizontal);
}

.wrapper.horizontal {
    flex-direction: row;
    align-items: center;
  }

.wrapper .setpoint,.wrapper .value,.wrapper .label,.wrapper .src {
    display: flex;
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    padding: 0px var(--instrument-components-readout-padding-horizontal);
  }

.wrapper .setpoint {
    color: var(--instrument-enhanced-secondary-color);
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
    transition: opacity 10ms ease-in-out;
  }

.wrapper.hide-setpoint .setpoint {
      opacity: 0;
      transition: opacity 0.2s ease-in-out;
    }

.wrapper.horizontal.enhanced .setpoint {
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

.wrapper .value {
    font-family: var(--global-typography-font-family);
    font-weight: var(
    --global-typography-instrument-value-regular-font-weight-active
  );
    font-size: var(--global-typography-instrument-value-regular-font-size);
    line-height: var(--global-typography-instrument-value-regular-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    padding: 0px var(--instrument-components-readout-padding-horizontal);
    justify-content: end;
  }

:is(.wrapper .value) .value-hint-zero {
      opacity: 0;
      color: var(--border-outline-color);
    }

:is(.wrapper .value) .value-blue {
      color: var(--instrument-enhanced-secondary-color);
    }

.wrapper.show-zero-padding .value-hint-zero {
      opacity: 1;
    }

.wrapper .label {
    justify-content: end;
    gap: var(--instrument-components-readout-icon-spacing);
    color: var(--element-neutral-color);
    text-wrap: nowrap;
  }

:is(.wrapper .label) .tag {
      font-family: var(--global-typography-font-family);
      font-weight: var(--global-typography-instrument-label-font-weight);
      font-size: var(--global-typography-instrument-label-font-size);
      line-height: var(--global-typography-instrument-label-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
      width: var(--obc-instrument-field-tag-width);
    }

:is(.wrapper .label) .unit {
      font-family: var(--global-typography-font-family);
      font-weight: var(--global-typography-instrument-unit-font-weight);
      font-size: var(--global-typography-instrument-unit-font-size);
      line-height: var(--global-typography-instrument-unit-line-height);
      font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    }

.wrapper.off .label {
    color: var(--element-inactive-color);
  }

.wrapper.horizontal.enhanced {
    height: 48px;
  }

.wrapper.horizontal.enhanced .label {
      flex-direction: column;
      align-items: start;
      justify-content: center;
      gap: 0;
    }

.wrapper.horizontal .label {
      align-items: start;
    }

.wrapper .src {
    font-family: var(--global-typography-font-family);
    font-weight: var(--global-typography-instrument-unit-font-weight);
    font-size: var(--global-typography-instrument-unit-font-size);
    line-height: var(--global-typography-instrument-unit-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--element-neutral-color);
    justify-content: end;
    width: var(--obc-instrument-field-source-width);
    box-sizing: content-box;
  }

.wrapper.off .src {
    color: var(--element-inactive-color);
  }

.wrapper.horizontal .src {
    justify-content: start;
  }

.wrapper.horizontal.enhanced .src {
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-body-font-weight);
    font-size: var(--global-typography-ui-body-font-size);
    line-height: var(--global-typography-ui-body-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.wrapper.neutral-color .value-blue {
      color: var(--element-neutral-color);
    }

.wrapper.off .value-blue {
      color: var(--element-inactive-color);
    }

.wrapper.enhanced .value {
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
    }

.wrapper .divider {
    height: var(--instrument-components-readout-divider-height-regular);
    width: 1px;
    background-color: var(--border-outline-color);
    border-radius: 1px;
    margin: 0
      calc(var(--instrument-components-readout-padding-horizontal) - 0.5px);
  }

.wrapper.regular .divider {
    height: var(--instrument-components-readout-divider-height-small);
  }

.wrapper:has(.src-picker) .src-divider {
    margin-right: 0;
  }

.wrapper .src:has(.src-picker) {
    padding-left: 0;
  }

.wrapper .src-picker {
    anchor-name: --src-picker;
  }

.wrapper .src-picker::part(visible-wrapper) {
    padding: 0;
    padding-left: calc(
      var(--instrument-components-readout-padding-horizontal) - 0.5px +
        var(--instrument-components-readout-icon-spacing)
    );
    border: 0;
  }

.wrapper .src-picker::part(label) {
    padding: 0;
    font-family: var(--font-family-main);
    font-weight: var(--global-typography-ui-body-font-weight);
    font-size: var(--global-typography-ui-body-font-size);
    line-height: var(--global-typography-ui-body-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
    color: var(--element-neutral-color);
  }

.wrapper.center .label {
  justify-content: center;
}

.src-picker-content {
  position: absolute;
  position-anchor: --src-picker;
  top: calc(anchor(bottom) - 8px);
  left: anchor(left);
}
`;var V8=Object.defineProperty;var A8=Object.getOwnPropertyDescriptor;var ht=(e,t,i,o)=>{var r=o>1?void 0:o?A8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)V8(t,i,r);return r};var z1=(e=>{e["regular"]="regular";e["enhanced"]="enhanced";return e})(z1||{});var ot=class extends k{constructor(){super(...arguments);this.size="regular";this.hasSetpoint=false;this.hasSrc=false;this.maxDigits=1;this.showZeroPadding=false;this.fractionDigits=0;this.tag="";this.unit="";this.src="";this.neutralColor=false;this.horizontal=false;this.center=false;this.labelOnly=false;this.off=false;this.autoHideSetpoint=false;this.autoHideDeadband=0}dashedGenerator(){const e=this.showZeroPadding?Math.max(this.maxDigits,1):1;if(this.fractionDigits<1){return"-".repeat(e)}else{const t=e-this.fractionDigits;return"-".repeat(Math.max(t,1))+"."+"-".repeat(this.fractionDigits)}}render(){const e=this.hasSetpoint&&this.autoHideSetpoint&&this.setpoint!==void 0&&this.value!==void 0&&Math.abs(this.setpoint-this.value)<=this.autoHideDeadband;return h`
      <div
        class=${J({wrapper:true,[this.size]:true,"neutral-color":this.neutralColor,off:this.off,horizontal:this.horizontal,center:this.center,"left-aligned":this.labelOnly||this.horizontal&&!this.hasSetpoint,"hide-setpoint":e,"show-zero-padding":this.showZeroPadding})}
      >
        ${this.horizontal&&this.size==="regular"?h`<div class="label">
              <div class="tag" part="tag">${this.tag}</div>
            </div>`:w}
        ${this.hasSetpoint?h`<div class="setpoint">
              <svg
                class="setpoint-arrow"
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fill="var(--instrument-enhanced-secondary-color)"
                  d="M4.66797 4.80263C4.66797 4.14363 5.45194 3.76746 6.0013 4.16286L10.4456 7.17243C11.0312 7.56899 11.0314 8.43154 10.4459 8.82828L6.0013 11.8401C5.45194 12.2355 4.66797 11.8593 4.66797 11.2003L4.66797 4.80263Z"
                  fill="var(--instrument-enhanced-primary-color)"
                />
              </svg>
              <div class="setpoint-value">${this.setpointValueBlueNumbers}</div>
            </div>`:w}
        ${this.horizontal&&!this.labelOnly&&this.hasSetpoint?h`<div class="divider"></div>`:w}
        ${!this.labelOnly?h` <div class="value">
              ${this.off?h`<div class="value-blue">
                    <slot name="off-value">OFF</slot>
                  </div>`:h` <div class="value-hint-zero">${this.hintZeros}</div>
                    <div class="value-blue">${this.valueBlueNumbers}</div>`}
            </div>`:w}
        <div class="label" part="label">
          ${this.horizontal&&this.size==="regular"?w:h`<div class="tag" part="tag">${this.tag}</div>`}
          <div class="unit">${this.unit}</div>
        </div>
        ${this.hasSrc&&this.horizontal?h`<div class="divider src-divider"></div>`:w}
        ${this.hasSrc?h`<div class="src">${this.src}</div>`:w}
      </div>
    `}get setpointValueBlueNumbers(){if(this.setpoint===void 0){return this.dashedGenerator()}return this.setpoint.toFixed(this.fractionDigits)}get valueBlueNumbers(){if(this.value===void 0){return this.dashedGenerator()}return this.value.toFixed(this.fractionDigits)}get hintZeros(){if(this.value===void 0||this.value<0){return""}const e=this.valueBlueNumbers.length;const t=this.maxDigits-e;if(t>0){return"0".repeat(t)}return""}};ot.styles=Q(S0);ht([l({type:String})],ot.prototype,"size",2);ht([l({type:Number})],ot.prototype,"setpoint",2);ht([l({type:Boolean})],ot.prototype,"hasSetpoint",2);ht([l({type:Boolean})],ot.prototype,"hasSrc",2);ht([l({type:Number})],ot.prototype,"value",2);ht([l({type:Number})],ot.prototype,"maxDigits",2);ht([l({type:Boolean})],ot.prototype,"showZeroPadding",2);ht([l({type:Number})],ot.prototype,"fractionDigits",2);ht([l({type:String})],ot.prototype,"tag",2);ht([l({type:String})],ot.prototype,"unit",2);ht([l({type:String})],ot.prototype,"src",2);ht([l({type:Boolean})],ot.prototype,"neutralColor",2);ht([l({type:Boolean})],ot.prototype,"horizontal",2);ht([l({type:Boolean})],ot.prototype,"center",2);ht([l({type:Boolean})],ot.prototype,"labelOnly",2);ht([l({type:Boolean})],ot.prototype,"off",2);ht([l({type:Boolean})],ot.prototype,"autoHideSetpoint",2);ht([l({type:Number})],ot.prototype,"autoHideDeadband",2);ot=ht([x("obc-instrument-field")],ot);var Z8=Object.defineProperty;var T8=Object.getOwnPropertyDescriptor;var _r=(e,t,i,o)=>{var r=o>1?void 0:o?T8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)Z8(t,i,r);return r};var Kt=class extends qo(k){constructor(){super(...arguments);this.speed=0;this.maxSpeed=100;this.minSpeed=0;this.showLabels=false;this.tickmarksInside=false;this.tickmarkInterval=20;this.priority=me.regular;this.needleType="full";this.speedAdvices=[];this.tickmarkStyle=He.regular;this.showReadout=false;this.maxAngle=180-45}getAngle(e){return e/this.maxSpeed*(180+45)-90}get minAngle(){return this.getAngle(this.minSpeed)-360}render(){const e=this.priority===me.enhanced?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)";const t=this.setpoint!==void 0?this.getAngle(this.setpoint):void 0;const i=this.maxSpeed.toFixed(1).length;return h`
      <div class="container">
        <obc-watch
          .touching=${this.touching}
          .angleSetpoint=${t}
          .newAngleSetpoint=${this.newSetpoint!==void 0?this.getAngle(this.newSetpoint):void 0}
          .atAngleSetpoint=${this.computeAtSetpoint(this.speed)}
          .angleSetpointAtZeroDeadband=${this.setpointAtZeroDeadband}
          .setpointOverride=${this.setpointOverride}
          .animateSetpoint=${this.animateSetpoint}
          .padding=${48}
          .tickmarks=${this.tickmarks}
          .tickmarksInside=${this.tickmarksInside}
          .tickmarkStyle=${this.tickmarkStyle}
          .advices=${this._advices}
          .areas=${[{startAngle:this.minAngle,endAngle:this.maxAngle,roundInsideCut:true,roundOutsideCut:true}]}
          .watchCircleType=${Lr.double}
          .barAreas=${[{startAngle:this.getAngle(0),endAngle:this.getAngle(this.speed),fillColor:e}]}
        ></obc-watch>
        <svg class="rudder" viewBox="-224 -224 448 448">${this.needle}</svg>
        ${this.showReadout?h`
              <obc-instrument-field
                class="speed-gauge-value"
                .size=${z1.enhanced}
                .neutralColor=${this.priority!==me.enhanced}
                .value=${this.speed}
                horizontal
                unit="KN"
                tag="STW"
                .fractionDigits=${1}
                .maxDigits=${i}
              ></obc-instrument-field>
            `:w}
      </div>
    `}get needle(){const e=this.priority===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";if(this.needleType==="full"){return c`<g transform="rotate(${this.getAngle(this.speed)}) translate(-256, -256)">
      <circle cx="256" cy="256" r="14" fill=${e}/>
      <rect x="250" y="96" width="12" height="192" rx="6" fill=${e}/>
      <rect x="252" y="98" width="8" height="188" rx="4" stroke=${e} fill=${e} stroke-width="4"/>
      </svg> 
`}else{return c`<g transform="rotate(${this.getAngle(this.speed)}) translate(-256, -256)">
<rect x="252" y="96" width="8" height="48" rx="4" fill=${e} stroke="var(--border-silhouette-color)"/>
</svg>
      `}}get tickmarks(){const e=[];const t=this.tickmarkInterval;if(t!==void 0&&t>0&&Number.isFinite(t)){for(let i=t;i<this.maxSpeed;i+=t){e.push({angle:this.getAngle(i),type:Te.primary,text:this.showLabels?i.toString():void 0})}if(this.showLabels&&this.maxSpeed%t===0){e.push({angle:this.getAngle(this.maxSpeed),type:Te.textOnly,text:this.showLabels?this.maxSpeed.toString():void 0})}for(let i=-t;i>this.minSpeed;i-=t){e.push({angle:this.getAngle(i),type:Te.main,text:this.showLabels?i.toString():void 0})}if(this.showLabels&&this.minSpeed%t===0){e.push({angle:this.getAngle(this.minSpeed),type:Te.textOnly,text:this.showLabels?this.minSpeed.toString():void 0})}}e.push({angle:this.getAngle(0),type:this.minSpeed<0?Te.main:Te.textOnly,text:this.showLabels?"0":void 0});return e}get _advices(){return this.speedAdvices.map(e=>{const t=this.getAngle(e.minSpeed);const i=this.getAngle(e.maxSpeed);let o=e.hinted?de.hinted:de.regular;if(this.speed>=e.minSpeed&&this.speed<=e.maxSpeed){o=de.triggered}return{minAngle:t,maxAngle:i,type:e.type,state:o,hideMinTickmark:e.minSpeed===this.minSpeed,hideMaxTickmark:e.maxSpeed===this.maxSpeed}})}};Kt.styles=L`
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

    obc-watch {
      anchor-name: --watch;
    }

    .speed-gauge-value {
      position: absolute;
      top: clamp(
        70%,
        calc(80% - (anchor-size(--watch height) - 200px) * 0.2),
        80%
      );
      left: 50%;
      transform: translateX(-50%);
      width: fit-content;
      height: fit-content;
    }
  `;_r([l({type:Number})],Kt.prototype,"speed",2);_r([l({type:Number})],Kt.prototype,"maxSpeed",2);_r([l({type:Number})],Kt.prototype,"minSpeed",2);_r([l({type:Boolean})],Kt.prototype,"showLabels",2);_r([l({type:Boolean})],Kt.prototype,"tickmarksInside",2);_r([l({type:Number})],Kt.prototype,"tickmarkInterval",2);_r([l({type:String})],Kt.prototype,"priority",2);_r([l({type:String})],Kt.prototype,"needleType",2);_r([l({type:Array,attribute:false})],Kt.prototype,"speedAdvices",2);_r([l({type:String})],Kt.prototype,"tickmarkStyle",2);_r([l({type:Boolean})],Kt.prototype,"showReadout",2);Kt=_r([x("obc-speed-gauge")],Kt);var _0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  width: fit-content;
  display: block;
}

.wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--maneuvering-components-poi-button-touch-target);
  height: var(--maneuvering-components-poi-button-touch-target);
  appearance: none;
  border: none;
  background: transparent;

  color: var(--on-flat-active-color);

  flex-shrink: 0;
  --label-y-offset: 16px;
  --label-x-offset: 12px;
}

.wrapper:has(.selection-frame) {
    --label-y-offset: 8px;
    --label-x-offset: 8px;
  }

.wrapper .visible-wrapper {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-direction: column;
    border: 1px solid transparent;
  }

.wrapper.type-flat .visible-wrapper {
      width: 36px;
      height: 36px;
    }

.wrapper.type-flat.has-alert {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

.wrapper.type-flat.has-alert .selection-frame {
        width: 44px;
        height: 44px;
      }

.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot {
    width: 64px;
    height: 64px;
  }

:is(.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .icon-wrapper {
      width: 36px;
      height: 36px;
    }

:is(.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .selection-frame {
      width: 43px;
      height: 43px;
    }

:is(.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .visible-wrapper {
      width: 52px;
      height: 52px;
      border-radius: 100%;
    }

.has-alert:is(.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

.has-alert:is(.wrapper.type-flat-large,.wrapper.type-large,.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .selection-frame {
        width: 60px;
        height: 60px;
      }

:is(.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .icon-wrapper {
      width: 24px;
      height: 24px;
    }

:is(.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .selection-frame {
      width: 55px;
      height: 55px;
    }

:is(.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot):has(.selection-frame) {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

.has-alert:is(.wrapper.type-flat-speed-rot,.wrapper.type-button-speed-rot) .selection-frame {
        width: 60px;
        height: 60px;
      }

.wrapper.type-large,.wrapper.type-button-speed-rot {
    --label-y-offset: 8px;
    --label-x-offset: 8px;
  }

:is(.wrapper.type-large,.wrapper.type-button-speed-rot) .selection-frame {
      width: 56px;
      height: 56px;
    }

:is(.wrapper.type-large,.wrapper.type-button-speed-rot):has(.selection-frame) {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot) {
            cursor: pointer;
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):focus {
            outline: none;
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot) .visible-wrapper {
            border-color: var(--normal-enabled-border-color);
            background-color: var(--normal-enabled-background-color);
            border-width: 1px;
            border-style: solid;
            cursor: pointer;
            --base-border-color: var(--normal-enabled-border-color);
            --base-background-color: var(--normal-enabled-background-color);
}

.activated:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot) .visible-wrapper {
            border-color: var(--normal-activated-border-color);
            background-color: var(--normal-activated-background-color);
            --base-border-color: var(--normal-activated-border-color);
            --base-background-color: var(--normal-activated-background-color);
}

@media (hover:hover) {

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):hover .visible-wrapper {
                        border-color: color-mix(in srgb, var(--normal-hover-border-color) calc(var(--obc-can-hover) * 100%), var(--base-border-color));
                        background-color: color-mix(in srgb, var(--normal-hover-background-color) calc(var(--obc-can-hover) * 100%), var(--base-background-color));
            }
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):active .visible-wrapper {
            border-color: var(--normal-pressed-border-color);
            background-color: var(--normal-pressed-background-color);
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):focus-visible .visible-wrapper {
            outline-color: var(--border-focus-color);
            outline-width: var(--global-size-spacing-border-weight-focusframe);
            outline-style: solid;
            border-color: var(--container-global-color);
            z-index: 1;
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):disabled .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

.disabled:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot) .visible-wrapper {
            border-color: var(--normal-disabled-border-color);
            background-color: var(--normal-disabled-background-color);
            cursor: not-allowed;
            color: var(--on-normal-disabled-color) !important;
}

:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot):disabled {
            cursor: not-allowed;
}

.disabled:is(.wrapper.type-button,.wrapper.type-large,.wrapper.type-button-speed-rot) {
            cursor: not-allowed;
}

.wrapper.type-button .visible-wrapper {
      width: var(--maneuvering-components-poi-button-visual-target-round);
      height: var(--maneuvering-components-poi-button-visual-target-round);
      border-radius: 100%;
    }

.wrapper.type-button {

    --label-y-offset: 8px;
    --label-x-offset: 8px;
  }

.wrapper.type-button:has(.selection-frame) {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

.wrapper.type-button:has(.selection-frame) .selection-frame {
        width: 40px;
        height: 40px;
      }

.wrapper.type-button.has-alert {
      --label-y-offset: 4px;
      --label-x-offset: 4px;
    }

.wrapper.type-button.has-alert .selection-frame {
        width: 44px;
        height: 44px;
      }

.icon-wrapper {
  width: 24px;
  height: 24px;
  position: relative;
}

.icon-wrapper .icon-silhouette,.icon-wrapper .icon-primary {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
  }

.icon-wrapper .icon-silhouette {
    stroke: var(--border-silhouette-color);
    stroke-width: 2;
    z-index: -1;
  }

.icon-wrapper .icon-primary {
    --element-active-color: var(--on-flat-active-color);
  }

.state-alarm .icon-primary {
    --element-active-color: var(--alert-alarm-outline-color);
  }

.state-alarm {
  color: var(--alert-alarm-outline-color);
}

.alert-ring {
  position: absolute;
  top: -3.5px;
  left: -3.5px;
  right: -3.5px;
  bottom: -3.5px;
  border-radius: 100%;
  border: 5px solid var(--alert-alarm-outline-color);
  outline: 4px solid var(--alert-alarm-color);
  outline-offset: -4.5px;
}

.state-caution .alert-ring {
    outline-color: var(--alert-caution-color);
    border-color: var(--alert-caution-outline-color);
  }

.state-warning .alert-ring {
    outline-color: var(--alert-warning-color);
    border-color: var(--alert-warning-outline-color);
  }

.number-wrapper,
.name-wrapper {
  position: absolute;
  top: calc(100% - var(--label-y-offset));
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
  color: var(--element-active-color);
  text-wrap: nowrap;
  transition:
    top 100ms ease,
    left 100ms ease,
    right 100ms ease;
}

.number-wrapper {
  right: calc(100% - var(--label-x-offset));
}

.name-wrapper {
  left: calc(100% - var(--label-x-offset));
}

:is(.state-active,.wrapper:has(.selection-frame),.state-warning,.state-caution,.state-alarm) .number-wrapper,:is(.state-active,.wrapper:has(.selection-frame),.state-warning,.state-caution,.state-alarm) .name-wrapper {
    font-family: var(--global-typography-font-family);
    font-weight: var(
    --global-typography-instrument-value-small-font-weight-active
  );
    font-size: var(--global-typography-instrument-value-small-font-size);
    line-height: var(--global-typography-instrument-value-small-line-height);
    font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  }

.selection-frame {
  position: absolute;
  top: 0;
  left: 0;
  margin: auto;
  bottom: 0;
  right: 0;
  width: 31px;
  height: 31px;
  border-radius: 4px;
  transition:
    width 100ms ease,
    height 100ms ease;

  border: 1.5px solid var(--element-active-color);
  clip-path: polygon(
    /* top left */ 8px 0,
    0 0,
    0 8px,
    8px 8px,
    /* top right */ calc(100% - 8px) 8px,
    calc(100% - 8px) 0,
    100% 0,
    100% 8px,
    calc(100% - 8px) 8px,
    /* bottom right */ calc(100% - 8px) calc(100% - 8px),
    calc(100% - 8px) 100%,
    100% 100%,
    100% calc(100% - 8px),
    calc(100% - 8px) calc(100% - 8px),
    /* bottom left */ 8px calc(100% - 8px),
    0 calc(100% - 8px),
    0 100%,
    8px 100%,
    8px calc(100% - 8px)
  );
}

.course-arrow {
  position: absolute;
  left: 50%;
  transform: translate(-50%, -50%) rotate(calc(var(--course)));
  transform-origin: center bottom;
}

.cross-line {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) rotate(calc(var(--heading)));
  transform-origin: center center;
}

.vessel-image-wrapper {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) rotate(calc(var(--heading)));
  transform-origin: center center;
}

.vessel-image-wrapper > slot {
    width: var(--image-size);
    height: var(--image-size);
  }

.vessel-image-wrapper > svg {
    width: calc(var(--image-size) * 160 / 136.87);
    height: calc(var(--image-size) * 160 / 136.87);
  }
`;var P8=Object.defineProperty;var z8=Object.getOwnPropertyDescriptor;var Xt=(e,t,i,o)=>{var r=o>1?void 0:o?z8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)P8(t,i,r);return r};var Bt=class extends k{constructor(){super(...arguments);this.heading=0;this.course=0;this.speedIndicator="two";this.turnRate=0;this.number=void 0;this.name=void 0;this.state="enabled";this.type="flat";this.selected=false;this.courseArrowPx=void 0;this.ownShipIndicator=false;this.vesselImage=null;this.vesselImageSize=80}render(){const e=["button","large","button-speed-rot"].includes(this.type);const t=e?We`button`:We`div`;const i=["alarm","warning","caution"].includes(this.state);return ce`
      <${t}
        class=${J({wrapper:true,[`state-${this.state}`]:true,[`type-${this.type}`]:true,"has-alert":i,selected:this.selected})}
        style="--heading: ${this.heading}deg;"
      >
      ${this.getVesselImageIcon()}
      ${this.getCourseArrowIcon()}
       ${this.getOwnShipIndicatorIcon()}
        <div class="visible-wrapper" style="transform: rotate(${this.heading}deg);">
          ${this.getTurnRateIcon()}
        <div
            class="icon-wrapper" 
          >
            <span class="icon-silhouette" part="icon-silhouette">
              <slot name="silhouette"></slot>
            </span>
            <span class="icon-primary" part="icon">
              <slot></slot>
            </span>

          </div>
          ${this.getSpeedIndicatorIcon()}
          ${i?ce`<div class="alert-ring"></div>`:w}
        </div>
        ${this.selected?ce`<div class="selection-frame"></div>`:w}
        ${this.number?ce`<div class="number-wrapper">
                <slot name="number">${this.number}</slot>
              </div>`:w}
        ${this.name?ce`<div class="name-wrapper">
                <slot name="name">${this.name}</slot>
              </div>`:w}
        
      </${t}>
    `}getSpeedIndicatorIcon(){const e=["button-speed-rot","flat-speed-rot"].includes(this.type);if(!e){return w}let t=[];switch(this.speedIndicator){case"one":t=[0];break;case"two":t=[-2,2];break;case"three":t=[-4,0,4];break}let i=void 0;if(this.speedIndicator==="stopped"){i=In`
        <circle cx="0" cy="0" r="4" fill="none" stroke="currentColor" stroke-width="1.5" />
      `}else if(this.speedIndicator==="anchored"){return In`
      <svg width="16" height="12" viewBox="0 0 16 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M8.75 3.25H10.75V4.75H8.75V8.38379C8.81975 8.36184 8.88925 8.33765 8.95703 8.30957C9.26022 8.18394 9.53551 7.99964 9.76758 7.76758C9.99964 7.53551 10.1839 7.26022 10.3096 6.95703C10.4352 6.65372 10.5 6.3283 10.5 6H12C12 6.52517 11.8962 7.04506 11.6953 7.53027C11.4943 8.01558 11.1996 8.45669 10.8281 8.82812C10.4567 9.19956 10.0156 9.49429 9.53027 9.69531C9.04506 9.89624 8.52517 10 8 10C7.47483 10 6.95494 9.89624 6.46973 9.69531C5.98442 9.49429 5.54331 9.19956 5.17188 8.82812C4.80044 8.45669 4.50571 8.01558 4.30469 7.53027C4.10376 7.04506 4 6.52517 4 6H5.5C5.5 6.3283 5.56479 6.65372 5.69043 6.95703C5.81606 7.26022 6.00036 7.53551 6.23242 7.76758C6.46449 7.99964 6.73978 8.18394 7.04297 8.30957C7.11075 8.33765 7.18025 8.36184 7.25 8.38379V4.75H5.25V3.25H7.25V1.25H8.75V3.25Z" fill="currentColor" />
      </svg>
      `}return ce`
      <svg
        width="16"
        height="12"
        viewBox="-8 -6 16 12"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        ${t.map(o=>In`
          <line
            x1="${o}"
            y1="-3"
            x2="${o}"
            y2="3"
            stroke-linecap="round"
            stroke-width="1.5"
            stroke="currentColor"
          />
        `)}
        ${i}
      </svg>
    `}getTurnRateIcon(){const e=["button-speed-rot","flat-speed-rot"].includes(this.type);if(!e){return w}const t=this.turnRate/100*12;const i=24;const o=-i*Math.cos(t*Math.PI/180)+i+3;const r=i*Math.sin(t*Math.PI/180)+8;return ce`
      <svg
        width="16"
        height="12"
        viewBox="0 0 16 12"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M8 9 V 3 A ${i} ${i} 0 0 1 ${r} ${o}"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    `}getCourseArrowIcon(){if(this.courseArrowPx===void 0){return w}const e=this.courseArrowPx;let t="var(--element-active-color)";if(this.state==="alarm"){t="var(--alert-alarm-color)"}return ce`
      <svg
        width="256"
        height=${e}
        viewBox="-128 0 256 ${e}"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        class="course-arrow"
        style="--course: ${this.course}deg; --color: ${t}"
      >
        <line
          x1="0"
          y1="24"
          x2="0"
          y2=${e}
          stroke-width="4"
          stroke="var(--border-silhouette-color)"
          stroke-linecap="round"
        />
        <line
          x1="0"
          y1="24"
          x2="0"
          y2=${e}
          stroke-width="2"
          stroke="var(--color)"
          stroke-linecap="square"
          stroke-dasharray="4 4"
          stroke-linejoin="square"
        />
        <g transform="translate(-12 0)">
          <path
            d="M11.5457 11.2919L13.3638 12.1253L13.3638 12.1252L11.5457 11.2919ZM12.4548 11.2919L10.6367 12.1252L10.6367 12.1253L12.4548 11.2919ZM16.7136 20.5829L18.5317 19.7496L18.5317 19.7495L16.7136 20.5829ZM15.8044 21.9999L15.8044 23.9999L15.805 23.9999L15.8044 21.9999ZM14.8953 21.4169L13.0772 22.2503L13.0774 22.2507L14.8953 21.4169ZM11.9998 15.1005L13.8178 14.2671L11.9994 10.3004L10.1816 14.2673L11.9998 15.1005ZM9.10522 21.4169L10.9233 22.2504L10.9234 22.2501L9.10522 21.4169ZM8.19604 21.9999L8.19604 23.9999L8.1964 23.9999L8.19604 21.9999ZM7.28687 20.5829L5.46877 19.7495L5.46874 19.7496L7.28687 20.5829ZM11.5457 2.2919L13.3638 3.12527L13.3638 3.12521L11.5457 2.2919ZM12.4548 2.2919L10.6367 3.12521L10.6367 3.12527L12.4548 2.2919ZM16.7136 11.5829L18.5317 10.7496L18.5317 10.7495L16.7136 11.5829ZM15.8044 12.9999L15.8044 14.9999L15.805 14.9999L15.8044 12.9999ZM14.8953 12.4169L13.0772 13.2503L13.0774 13.2507L14.8953 12.4169ZM11.9998 6.10049L13.8178 5.26706L11.9994 1.30035L10.1816 5.2673L11.9998 6.10049ZM9.10522 12.4169L10.9233 13.2504L10.9234 13.2501L9.10522 12.4169ZM8.19604 12.9999L8.19604 14.9999L8.19643 14.9999L8.19604 12.9999ZM7.28687 11.5829L5.46877 10.7495L5.46874 10.7496L7.28687 11.5829ZM11.5457 11.2919L13.3638 12.1252C12.829 13.2919 11.1714 13.2919 10.6367 12.1252L12.4548 11.2919L14.273 10.4586C13.3817 8.5141 10.6187 8.5141 9.72752 10.4586L11.5457 11.2919ZM12.4548 11.2919L10.6367 12.1253L14.8955 21.4163L16.7136 20.5829L18.5317 19.7495L14.2729 10.4585L12.4548 11.2919ZM16.7136 20.5829L14.8955 21.4162C14.5917 20.7534 15.076 20.0001 15.8039 19.9999L15.8044 21.9999L15.805 23.9999C17.9899 23.9993 19.4426 21.737 18.5317 19.7496L16.7136 20.5829ZM15.8044 21.9999V19.9999C16.1945 19.9999 16.5498 20.227 16.7132 20.5831L14.8953 21.4169L13.0774 22.2507C13.5666 23.3174 14.6325 23.9999 15.8044 23.9999V21.9999ZM14.8953 21.4169L16.7133 20.5835L13.8178 14.2671L11.9998 15.1005L10.1817 15.9339L13.0772 22.2503L14.8953 21.4169ZM11.9998 15.1005L10.1816 14.2673L7.28704 20.5837L9.10522 21.4169L10.9234 22.2501L13.8179 15.9337L11.9998 15.1005ZM9.10522 21.4169L7.28718 20.5834C7.45077 20.2266 7.80642 20 8.19569 19.9999L8.19604 21.9999L8.1964 23.9999C9.36748 23.9997 10.4339 23.3179 10.9233 22.2504L9.10522 21.4169ZM8.19604 21.9999L8.19604 19.9999C8.92502 19.9999 9.40845 20.7541 9.10499 21.4162L7.28687 20.5829L5.46874 19.7496C4.55809 21.7365 6.00978 23.9999 8.19604 23.9999V21.9999ZM7.28687 20.5829L9.10496 21.4163L13.3638 12.1253L11.5457 11.2919L9.72755 10.4585L5.46877 19.7495L7.28687 20.5829ZM11.5457 2.2919L13.3638 3.12521C12.829 4.2919 11.1714 4.2919 10.6367 3.12521L12.4548 2.2919L14.273 1.45859C13.3817 -0.485895 10.6187 -0.485895 9.72752 1.45859L11.5457 2.2919ZM12.4548 2.2919L10.6367 3.12527L14.8955 12.4163L16.7136 11.5829L18.5317 10.7495L14.2729 1.45852L12.4548 2.2919ZM16.7136 11.5829L14.8955 12.4162C14.5917 11.7534 15.076 11.0001 15.8039 10.9999L15.8044 12.9999L15.805 14.9999C17.9899 14.9993 19.4427 12.7371 18.5317 10.7496L16.7136 11.5829ZM15.8044 12.9999V10.9999C16.1946 10.9999 16.5498 11.227 16.7131 11.5831L14.8953 12.4169L13.0774 13.2507C13.5666 14.3174 14.6325 14.9999 15.8044 14.9999V12.9999ZM14.8953 12.4169L16.7133 11.5835L13.8178 5.26706L11.9998 6.10049L10.1817 6.93392L13.0772 13.2503L14.8953 12.4169ZM11.9998 6.10049L10.1816 5.2673L7.28704 11.5837L9.10522 12.4169L10.9234 13.2501L13.8179 6.93368L11.9998 6.10049ZM9.10522 12.4169L7.28717 11.5834C7.45078 11.2265 7.80645 11 8.19566 10.9999L8.19604 12.9999L8.19643 14.9999C9.36745 14.9997 10.4339 14.3179 10.9233 13.2504L9.10522 12.4169ZM8.19604 12.9999V10.9999C8.92502 10.9999 9.40845 11.7541 9.10499 12.4162L7.28687 11.5829L5.46874 10.7496C4.55809 12.7365 6.00978 14.9999 8.19604 14.9999V12.9999ZM7.28687 11.5829L9.10496 12.4163L13.3638 3.12527L11.5457 2.2919L9.72755 1.45852L5.46877 10.7495L7.28687 11.5829Z"
            fill="var(--border-silhouette-color)"
          />
          <path
            d="M11.5457 11.2919C11.7239 10.903 12.2766 10.903 12.4548 11.2919L16.7136 20.5829C17.0172 21.2452 16.5329 21.9997 15.8044 21.9999C15.4135 21.9999 15.0582 21.7722 14.8953 21.4169L11.9998 15.1005L9.10522 21.4169C8.94231 21.7722 8.58695 21.9998 8.19604 21.9999C7.4674 21.9999 6.98327 21.2453 7.28687 20.5829L11.5457 11.2919ZM11.5457 2.2919C11.7239 1.903 12.2766 1.903 12.4548 2.2919L16.7136 11.5829C17.0172 12.2452 16.5329 12.9997 15.8044 12.9999C15.4135 12.9999 15.0582 12.7722 14.8953 12.4169L11.9998 6.10049L9.10522 12.4169C8.94232 12.7722 8.58695 12.9998 8.19604 12.9999C7.4674 12.9999 6.98327 12.2453 7.28687 11.5829L11.5457 2.2919Z"
            fill="var(--color)"
          />
        </g>
      </svg>
    `}getOwnShipIndicatorIcon(){if(!this.ownShipIndicator){return w}return ce`
      <svg
        width="64"
        height="256"
        viewBox="-32 -128 64 256"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        class="cross-line"
      >
        <circle cx="0" cy="0" r="2" fill="var(--element-active-color)" />
        <line
          x1="-32"
          x2="-4"
          y1="0"
          y2="0"
          stroke="var(--element-active-color)"
          stroke-width="1"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <line
          x1="32"
          x2="4"
          y1="0"
          y2="0"
          stroke="var(--element-active-color)"
          stroke-width="1"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <line
          x1="0"
          x2="0"
          y1="-4"
          y2="-128"
          stroke="var(--element-active-color)"
          stroke-width="1"
          stroke-linecap="round"
          stroke-linejoin="round"
        />

        <line
          x1="0"
          x2="0"
          y1="4"
          y2="128"
          stroke="var(--element-active-color)"
          stroke-width="1"
          stroke-dasharray="1 2"
        />
      </svg>
    `}getVesselImageIcon(){if(!this.vesselImage){return ce`<div
        class="vessel-image-wrapper"
        style="--image-size: ${this.vesselImageSize}px;"
        part="vessel-image-wrapper"
      >
        <slot name="vessel-image"></slot>
      </div>`}return ce`<div
      class="vessel-image-wrapper"
      style="--image-size: ${this.vesselImageSize}px;"
      part="vessel-image-wrapper"
    >
      ${ca[this.vesselImage]}
    </div>`}};Bt.styles=Q(_0);Xt([l({type:Number})],Bt.prototype,"heading",2);Xt([l({type:Number})],Bt.prototype,"course",2);Xt([l({type:String})],Bt.prototype,"speedIndicator",2);Xt([l({type:Number})],Bt.prototype,"turnRate",2);Xt([l({type:Number})],Bt.prototype,"number",2);Xt([l({type:String})],Bt.prototype,"name",2);Xt([l({type:String})],Bt.prototype,"state",2);Xt([l({type:String})],Bt.prototype,"type",2);Xt([l({type:Boolean})],Bt.prototype,"selected",2);Xt([l({type:Number})],Bt.prototype,"courseArrowPx",2);Xt([l({type:Boolean})],Bt.prototype,"ownShipIndicator",2);Xt([l({type:String})],Bt.prototype,"vesselImage",2);Xt([l({type:Number})],Bt.prototype,"vesselImageSize",2);Bt=Xt([x("obc-chart-object-vessel-button")],Bt);var V0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

:host {
  display: inline-flex;
}

* {
  box-sizing: border-box;
}

.wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  filter: drop-shadow(0px 2px 6px rgba(0, 0, 0, 0.5));
}

.wrapper.fixed-size {
  width: 256px;
  height: 256px;
}

.center {
  display: flex;
  align-items: stretch;
}

.wrapper.fixed-size .center {
  flex: 1 0 0;
  min-height: 0;
  min-width: 0;
  width: 100%;
}

.content-box {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  background-color: var(--overlay-container-background-color);
  border: 1px solid var(--overlay-border-outline-color);
  border-radius: 6px;
  position: relative;
}

.wrapper.interactive .content-box {
  cursor: pointer;
}

.wrapper.fixed-size .content-box {
  flex: 1 0 0;
  min-height: 0;
  min-width: 0;
}

obc-poi-card-header::part(wrapper) {
  border-radius: 5px 5px 0 0;
}

.content {
  display: flex;
  flex-direction: column;
  overflow: clip;
  border-radius: 0 0 5px 5px;
}

.wrapper.fixed-size .content {
  flex: 1 0 0;
  min-height: 0;
  min-width: 0;
}

.pointer-container {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.pointer-container.top,
.pointer-container.bottom {
  width: 100%;
}

.pointer-container.top svg,
.pointer-container.bottom svg {
  display: block;
}

.pointer-container.left,
.pointer-container.right {
  align-self: center;
}

.pointer-container.left svg,
.pointer-container.right svg {
  display: block;
}

.wrapper.interactive .content-box:focus-visible {
  outline: none;
}

.wrapper.interactive .content-box:focus-visible::before {
  content: "";
  position: absolute;
  inset: -1px;
  border: 1px solid var(--overlay-border-outline-color);
  border-radius: 7px;
  pointer-events: none;
}

.wrapper.interactive .content-box:focus-visible::after {
  content: "";
  position: absolute;
  inset: 0;
  border: 1px solid var(--border-focus-color);
  border-radius: 6px;
  pointer-events: none;
}

.alert-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: 6px;
}

.ring-outer {
  position: absolute;
  inset: -1px;
  border: 1px solid var(--overlay-border-outline-color);
  border-radius: 7px;
}

.ring-middle.alert {
  position: absolute;
  inset: 0;
  border: 1px solid var(--alert-caution-color);
  border-radius: 6px;
}

.ring-inner {
  position: absolute;
  inset: 1px;
  border: 1px solid var(--alert-caution-outline-color);
  border-radius: 5px;
}
`;var A0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.wrapper {
  display: flex;
  position: relative;
  width: 100%;
  user-select: none;
}

.tag-container {
  display: flex;
  flex: 1 0 0;
  justify-content: center;
  min-height: var(--maneuvering-components-poi-id-tag-container-height);
}

.wrapper.variant-condensed {
  background-color: var(--overlay-container-global-color);
  border-bottom: 1px solid var(--border-outline-color);
  height: var(--global-size-spacing-selection-size-min, 24px);
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.wrapper.variant-regular {
  background-color: var(--overlay-container-global-color);
  border-bottom: 1px solid var(--border-outline-color);
  align-items: flex-start;
  gap: 8px;
}

.wrapper.variant-regular .leading-icon {
    color: var(--element-neutral-color);
  }

.wrapper.variant-detailed {
  background-color: var(--container-global-color);
  border-bottom: 1px solid var(--indent-enabled-border-color);
  align-items: center;
}

.id-container {
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  z-index: 1;
  left: 8px;
  top: 0;
  bottom: 0;
}

.wrapper.variant-detailed .id-container {
  top: 4px;
  bottom: auto;
  height: var(--global-size-spacing-visual-target-min, 32px);
  align-items: flex-start;
}

.index-badge {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background-color: var(--normal-enabled-background-color);
  border: 1px solid var(--normal-enabled-border-color);
  border-radius: 50%;
  width: var(--maneuvering-components-poi-id-tag-min-size);
  height: var(--maneuvering-components-poi-id-tag-min-size);
}

.index-badge.tag-style {
  box-sizing: border-box;
  background-color: var(--overlay-container-global-color);
  border: 1px solid rgba(0, 0, 0, 0.3);
  min-width: var(--maneuvering-components-poi-id-tag-min-size);
}

.index-text {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-label-active-font-weight);
  font-size: var(--global-typography-ui-label-active-font-size);
  line-height: var(--global-typography-ui-label-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-active-color);
  text-align: center;
}

.header-container {
  display: flex;
  flex: 1 0 0;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.wrapper.variant-condensed .header-container {
  padding-right: 8px;
}

.wrapper.variant-regular .header-container {
  height: 32px;
}

.icon-container {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px 0;
  flex-shrink: 0;
}

.icon-container ::slotted(*) {
  width: var(--global-size-spacing-icon-icon-size-regular, 24px);
  height: var(--global-size-spacing-icon-icon-size-regular, 24px);
}

.title {
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
  color: var(--element-active-color);
  text-align: center;
  flex-shrink: 0;
}

.title.detailed-title {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-bold);
  font-size: var(--global-typography-ui-body-active-font-size);
  line-height: var(--global-typography-ui-body-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  letter-spacing: 0;
  text-align: left;
}

.source-badge {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--indent-enabled-background-color);
  border: 1px solid var(--indent-enabled-border-color);
  border-radius: 2px;
  min-width: 40px;
  padding: 0 8px;
  flex-shrink: 0;
}

.wrapper.variant-regular .source-badge,
.wrapper.variant-condensed .source-badge {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
}

.wrapper.variant-regular .source-badge {
  right: 8px;
}

.wrapper.variant-condensed .source-badge {
  right: 4px;
}

.source-text {
  font-family: var(--font-family-main);
  font-weight: var(--global-typography-ui-label-active-font-weight);
  font-size: var(--global-typography-ui-label-active-font-size);
  line-height: var(--global-typography-ui-label-active-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  text-align: center;
}

.wrapper.variant-regular .source-text,
.wrapper.variant-condensed .source-text {
  color: var(--element-active-color);
}

.wrapper.variant-detailed .source-text {
  color: var(--element-neutral-color);
}

.detailed-content {
  display: flex;
  flex: 1 0 0;
  align-items: center;
  min-height: 0;
  min-width: 0;
  padding: 0 8px;
}

.poi-container {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.text-container {
  display: flex;
  flex-direction: column;
  flex: 1 0 0;
  align-items: flex-start;
  min-height: 0;
  min-width: 0;
  padding-right: 16px;
  white-space: nowrap;
  text-align: center;
}

.description {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
  padding-right: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.meta-container {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  width: 40px;
}

.meta-container .source-badge {
  margin: 4px 0;
}

.timestamp {
  font-family: var(--font-family-main);
  font-weight: var(--font-weight-regular);
  font-size: var(--global-typography-ui-label-font-size);
  line-height: var(--global-typography-ui-label-line-height);
  font-feature-settings:
    "liga" off,
    "clig" off,
    "ss04" on;
  color: var(--element-neutral-color);
  text-align: center;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.close-button {
  flex-shrink: 0;
}
`;var Z0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

* {
  box-sizing: border-box;
}

:host {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.is-large {
  width: var(--maneuvering-components-poi-button-large-touch-target, 64px);
  height: var(--maneuvering-components-poi-button-large-touch-target, 64px);
}

.is-indicator.is-static .icon-container,
.is-indicator.is-activated .icon-container,
.is-indicator.is-overlapped .icon-container {
  filter: none;
}

.wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  --obc-poi-touch-target: var(
    --maneuvering-components-poi-button-touch-target,
    48px
  );
  --obc-poi-frame-size: var(
    --maneuvering-components-poi-button-visual-target-round
  );
  --obc-poi-bottom-offset: calc(
    (var(--obc-poi-touch-target) - var(--obc-poi-frame-size)) / 2
  );
  --obc-poi-icon-size: var(--maneuvering-components-poi-button-icon-size);
  --obc-poi-icon-size-overlap: var(
    --maneuvering-components-poi-button-icon-size-overlap
  );
  --obc-poi-size-transition-duration: var(--obc-poi-transition-duration, 0.1s);
  --obc-poi-color-transition-duration: var(--obc-poi-transition-duration, 0.1s);
}

.wrapper.interactive {
  cursor: pointer;
}

.is-large {
  --obc-poi-touch-target: var(
    --maneuvering-components-poi-button-large-touch-target,
    64px
  );
}

.background-frame,
.activated-frame {
  position: absolute;
  border-radius: var(--maneuvering-components-poi-button-border-radius-round);
  bottom: var(--obc-poi-bottom-offset);
  opacity: var(--obc-poi-object-frame-opacity, 1);
  box-shadow: var(--obc-poi-object-shadow, none);
  transition:
    opacity var(--obc-poi-opacity-transition-duration, 0.1s) ease-out,
    width var(--obc-poi-size-transition-duration, 0.1s) ease-out,
    height var(--obc-poi-size-transition-duration, 0.1s) ease-out,
    background-color var(--obc-poi-color-transition-duration, 0.1s) ease-out,
    border-color var(--obc-poi-color-transition-duration, 0.1s) ease-out,
    bottom var(--obc-poi-size-transition-duration, 0.1s) ease-out;
}

.background-frame {
  overflow: hidden;
}

.activated-frame {
  border: 4px solid var(--overlay-border-activated-color);
}

.is-square .background-frame,
.is-square .activated-frame {
  border-radius: var(--maneuvering-components-poi-button-border-radius-square);
}

.type-regular .background-frame,
.type-indicator .background-frame,
.type-regular .activated-frame,
.type-indicator .activated-frame {
  width: var(--maneuvering-components-poi-button-visual-target-round);
  height: var(--maneuvering-components-poi-button-visual-target-round);
}

.type-large {
  --obc-poi-frame-size: var(
    --maneuvering-components-poi-button-large-visual-target-round
  );
  --obc-poi-icon-size: var(--maneuvering-components-poi-button-large-icon-size);
  --obc-poi-icon-size-overlap: var(
    --maneuvering-components-poi-button-large-icon-size-overlap
  );
}

.type-large .background-frame,
.type-large .activated-frame {
  width: var(--maneuvering-components-poi-button-large-visual-target-round);
  height: var(--maneuvering-components-poi-button-large-visual-target-round);
}

.type-n-up {
  --obc-poi-frame-size: var(
    --maneuvering-components-poi-button-visual-target-square
  );
}

.type-n-up .background-frame,
.type-n-up .activated-frame {
  width: var(--maneuvering-components-poi-button-visual-target-square);
  height: var(--maneuvering-components-poi-button-visual-target-square);
}

.type-n-up-large {
  --obc-poi-frame-size: var(
    --maneuvering-components-poi-button-large-visual-target-square
  );
  --obc-poi-icon-size: var(--maneuvering-components-poi-button-large-icon-size);
  --obc-poi-icon-size-overlap: var(
    --maneuvering-components-poi-button-large-icon-size-overlap
  );
}

.type-n-up-large .background-frame,
.type-n-up-large .activated-frame {
  width: var(--maneuvering-components-poi-button-large-visual-target-square);
  height: var(--maneuvering-components-poi-button-large-visual-target-square);
}

.is-overlapped {
  --obc-poi-bottom-offset: var(
    --maneuvering-components-poi-button-overlap-offset-margin-round
  );
  --obc-poi-icon-scale: calc(
    var(--obc-poi-icon-size-overlap) / var(--obc-poi-icon-size)
  );
}

.is-overlapped .background-frame {
  width: var(--maneuvering-components-poi-button-visual-target-round-overlap);
  height: var(--maneuvering-components-poi-button-visual-target-round-overlap);
}

.is-large.is-overlapped .background-frame {
  width: var(
    --maneuvering-components-poi-button-large-visual-target-round-overlap
  );
  height: var(
    --maneuvering-components-poi-button-large-visual-target-round-overlap
  );
}

.is-square.is-overlapped .background-frame {
  width: var(--maneuvering-components-poi-button-visual-target-square-overlap);
  height: var(--maneuvering-components-poi-button-visual-target-square-overlap);
}

.is-square.is-large.is-overlapped .background-frame {
  width: var(
    --maneuvering-components-poi-button-large-visual-target-square-overlap
  );
  height: var(
    --maneuvering-components-poi-button-large-visual-target-square-overlap
  );
}

.is-indicator.is-overlapped .background-frame {
  width: 24px;
  height: 24px;
}

.style-regular .background-frame {
  background-color: var(--overlay-container-background-color);
  border: 1px solid var(--overlay-border-outline-color);
}

.style-categorical .background-frame {
  background-color: var(--base-blue-100);
  border: 1px solid var(--base-blue-200);
}

.style-categorical.is-overlapped .background-frame {
  border: 1px solid var(--base-blue-050);
}

.style-regular.is-static .background-frame,
.style-regular.is-activated .background-frame {
  background-color: var(--normal-enabled-background-color);
  border: 1px solid var(--normal-enabled-border-color);
}

.is-indicator.is-activated .activated-frame {
  background-color: var(--overlay-border-activated-color);
}

.icon-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  transform: scale(var(--obc-poi-icon-scale, 1));
  transform-origin: center;
  transition:
    opacity var(--obc-poi-opacity-transition-duration, 0.1s) ease-out,
    transform var(--obc-poi-transition-duration, 0.1s) ease-out;
}

.type-regular .icon-container,
.type-indicator .icon-container,
.type-n-up .icon-container {
  width: var(--obc-poi-icon-size);
  height: var(--obc-poi-icon-size);
}

.type-large .icon-container,
.type-n-up-large .icon-container {
  width: var(--obc-poi-icon-size);
  height: var(--obc-poi-icon-size);
}

.icon-container ::slotted(*) {
  width: 100%;
  height: 100%;
}

.wrapper.style-regular .icon-container ::slotted(*) {
  color: var(--instrument-regular-secondary-color);
  --element-active-color: var(--instrument-regular-secondary-color);
}

.wrapper.style-regular.is-indicator .icon-container ::slotted(*) {
  color: var(--element-inactive-color);
  --element-active-color: var(--element-inactive-color);
}

.wrapper.style-regular.is-checked .icon-container ::slotted(*),
.wrapper.style-regular.is-activated .icon-container ::slotted(*) {
  color: var(--element-neutral-color);
  --element-active-color: var(--element-neutral-color);
}

.wrapper.style-regular.is-static .icon-container ::slotted(*) {
  color: var(--element-inactive-color);
  --element-active-color: var(--element-inactive-color);
}

.wrapper.style-regular.is-static.is-checked .icon-container ::slotted(*) {
  color: var(--element-neutral-color);
  --element-active-color: var(--element-neutral-color);
}

.wrapper.style-regular.state-caution .icon-container ::slotted(*),
.wrapper.style-regular.state-warning .icon-container ::slotted(*),
.wrapper.style-regular.state-alarm .icon-container ::slotted(*),
.wrapper.style-enhanced.state-caution .icon-container ::slotted(*),
.wrapper.style-enhanced.state-warning .icon-container ::slotted(*),
.wrapper.style-enhanced.state-alarm .icon-container ::slotted(*) {
  color: var(--element-active-color);
  --element-active-color: var(--element-active-color);
}

.style-enhanced .background-frame {
  background-color: var(--overlay-container-background-color);
  border: 1px solid var(--overlay-border-outline-color);
}

.style-enhanced.is-static .background-frame,
.style-enhanced.is-activated .background-frame {
  background-color: var(--normal-enabled-background-color);
  border: 1px solid var(--normal-enabled-border-color);
}

.wrapper.style-enhanced .icon-container ::slotted(*) {
  color: var(--instrument-enhanced-secondary-color);
  --element-active-color: var(--instrument-enhanced-secondary-color);
}

.wrapper.style-categorical .icon-container ::slotted(*) {
  color: var(--base-blue-500);
  --element-active-color: var(--base-blue-500);
  --element-active-inverted-color: var(--base-blue-100);
}

.is-indicator .icon-container ::slotted(*) {
  stroke: var(--indicator-stroke-color, rgb(255, 255, 255));
  stroke-width: var(--indicator-stroke-width, 2px);
  stroke-linejoin: round;
  paint-order: stroke fill;
  overflow: visible;
  --element-active-inverted-color: var(
    --indicator-stroke-color,
    rgb(255, 255, 255)
  );
}

.is-indicator.is-static .icon-container ::slotted(*),
.is-indicator.is-overlapped .icon-container ::slotted(*) {
  stroke: none;
  stroke-width: 0;
  paint-order: normal;
  overflow: hidden;
}

.is-indicator.has-placeholder-icon .indicator-placeholder-fill {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}

.is-indicator.has-placeholder-icon .indicator-placeholder-fill path {
  fill: var(--element-active-inverted-color);
}

.is-indicator.has-placeholder-icon .icon-container ::slotted(obi-placeholder) {
  position: relative;
  z-index: 1;
}

.is-indicator.style-categorical .icon-container ::slotted(*) {
  stroke: var(--base-blue-100);
}

.is-indicator.style-categorical .icon-container {
  --element-active-inverted-color: var(--base-blue-100);
}

.is-overlapped .icon-container {
  opacity: 0;
}

.wrapper.interactive .background-frame {
  transition:
    background-color var(--obc-poi-color-transition-duration, 0.1s) ease,
    border-color var(--obc-poi-color-transition-duration, 0.1s) ease;
}

:host(:hover) .wrapper.interactive:not(.is-indicator) .background-frame {
  background-color: var(--flat-hover-background-color);
}

:host(:active) .wrapper.interactive:not(.is-indicator) .background-frame {
  background-color: var(--flat-pressed-background-color);
}

.wrapper.interactive.is-indicator .background-frame {
  background-color: transparent;
  border-color: transparent;
}

:host(:hover) .wrapper.interactive.is-indicator .background-frame {
  background-color: var(--overlay-flat-hover-background-color);
  border-color: var(--overlay-flat-hover-border-color);
}

:host(:active) .wrapper.interactive.is-indicator .background-frame {
  background-color: var(--overlay-flat-active-background-color);
  border-color: var(--overlay-flat-active-border-color);
}

.wrapper:focus {
  outline: none;
}

.wrapper:focus-visible .background-frame {
  outline: 2px solid var(--element-active-color);
  outline-offset: 2px;
}
`;var B8=Object.defineProperty;var O8=Object.getOwnPropertyDescriptor;var ma=(e,t,i,o)=>{var r=o>1?void 0:o?O8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)B8(t,i,r);return r};var fo=(e=>{e["Indicator"]="indicator";e["Regular"]="regular";e["Large"]="large";e["NUp"]="n-up";e["NUpLarge"]="n-up-large";return e})(fo||{});var ms=(e=>{e["Regular"]="regular";e["Categorical"]="categorical";e["Enhanced"]="enhanced";return e})(ms||{});var B1=(e=>{e["Unchecked"]="unchecked";e["Checked"]="checked";e["StaticUnchecked"]="static-unchecked";e["StaticChecked"]="static-checked";e["Activated"]="activated";e["Overlapped"]="overlapped";e["Caution"]="caution";e["Warning"]="warning";e["Alarm"]="alarm";return e})(B1||{});var Ko=class extends k{constructor(){super(...arguments);this.type="regular";this.objectStyle="regular";this.state="unchecked";this.interactive=false;this.hasPlaceholderIcon=false}applyHostSize(){if(this.isLargeSize){this.style.width="var(--maneuvering-components-poi-button-large-touch-target, 64px)";this.style.height="var(--maneuvering-components-poi-button-large-touch-target, 64px)"}else{this.style.width="var(--maneuvering-components-poi-button-touch-target, 48px)";this.style.height="var(--maneuvering-components-poi-button-touch-target, 48px)"}}updated(e){if(e.has("type")){this.applyHostSize()}}connectedCallback(){super.connectedCallback();this.applyHostSize()}get isChecked(){return this.state==="checked"||this.state==="static-checked"}get isStatic(){return this.state==="static-unchecked"||this.state==="static-checked"}get isActivated(){return this.state==="activated"}get isOverlapped(){return this.state==="overlapped"}get isInteractive(){return this.interactive&&!this.isOverlapped}get isSquare(){return this.type==="n-up"||this.type==="n-up-large"}get isLargeSize(){return this.type==="large"||this.type==="n-up-large"}get isIndicator(){return this.type==="indicator"}handleKeyDown(e){if(!this.isInteractive)return;if(e.target!==e.currentTarget)return;if(e.key===" "){e.preventDefault()}else if(e.key==="Enter"&&!e.repeat){e.preventDefault();this.click()}}handleKeyUp(e){if(!this.isInteractive)return;if(e.target!==e.currentTarget)return;if(e.key===" "){e.preventDefault();this.click()}}handleSlotChange(e){const t=e.target;const i=t.assignedElements({flatten:true}).some(o=>o.tagName.toLowerCase()==="obi-placeholder");if(i!==this.hasPlaceholderIcon){this.hasPlaceholderIcon=i}}render(){const e={wrapper:true,[`type-${this.type}`]:true,[`style-${this.objectStyle}`]:true,[`state-${this.state}`]:true,"is-static":this.isStatic,"is-checked":this.isChecked,"is-activated":this.isActivated,"is-overlapped":this.isOverlapped,"is-square":this.isSquare,"is-large":this.isLargeSize,"is-indicator":this.isIndicator,"has-placeholder-icon":this.hasPlaceholderIcon,interactive:this.isInteractive};return h`
      <div
        class=${J(e)}
        role=${this.isInteractive?"button":w}
        tabindex=${this.isInteractive?"0":w}
        @keydown=${this.handleKeyDown}
        @keyup=${this.handleKeyUp}
      >
        ${this.isActivated?h`<div class="activated-frame" part="activated-frame"></div>`:w}
        ${!this.isIndicator||this.isOverlapped||this.isInteractive?h`<div class="background-frame" part="background-frame"></div>`:w}

        <div class="icon-container" part="icon-container">
          ${this.isIndicator&&this.hasPlaceholderIcon?h`<svg
                class="indicator-placeholder-fill"
                viewBox="0 0 24 24"
                aria-hidden="true"
                focusable="false"
              >
                <path d="M12 3L3 12L12 21L21 12L12 3Z"></path>
              </svg>`:w}
          <slot @slotchange=${this.handleSlotChange}></slot>
        </div>
      </div>
    `}};Ko.styles=Q(Z0);ma([l({type:String})],Ko.prototype,"type",2);ma([l({type:String})],Ko.prototype,"objectStyle",2);ma([l({type:String})],Ko.prototype,"state",2);ma([l({type:Boolean})],Ko.prototype,"interactive",2);ma([Ve()],Ko.prototype,"hasPlaceholderIcon",2);Ko=ma([x("obc-poi-object")],Ko);var D8=Object.defineProperty;var O1=(e,t,i,o)=>{var r=void 0;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=n(t,i,r)||r;if(r)D8(t,i,r);return r};var E8={"--overlay-container-background-color":"var(--base-blue-100)","--overlay-border-outline-color":"var(--base-blue-200)","--normal-enabled-background-color":"var(--base-blue-100)","--normal-enabled-border-color":"var(--base-blue-200)","--flat-enabled-background-color":"var(--base-blue-100)","--flat-enabled-border-color":"var(--base-blue-200)","--flat-hover-background-color":"color-mix(in srgb, var(--base-blue-100) 85%, white)","--flat-pressed-background-color":"color-mix(in srgb, var(--base-blue-100) 75%, white)"};var T0=class YT extends k{constructor(){super(...arguments);this.objectStyle=ms.Regular;this.state=B1.Unchecked;this.interactive=false}get icon(){return h`<slot></slot>`}get baseType(){return fo.Regular}get colorStyleVars(){if(this.objectStyle===ms.Categorical){return E8}return{}}render(){return h`<obc-poi-object
      exportparts="background-frame"
      style=${da(this.colorStyleVars)}
      .type=${this.baseType}
      .objectStyle=${this.objectStyle}
      .state=${this.state}
      ?interactive=${this.interactive}
    >
      ${this.icon}
    </obc-poi-object>`}};T0.styles=[L`
      :host {
        display: contents;
      }

      slot {
        display: flex;
        width: 100%;
        height: 100%;
        align-items: center;
        justify-content: center;
      }
    `];var ga=T0;O1([l({type:String})],ga.prototype,"objectStyle");O1([l({type:String})],ga.prototype,"state");O1([l({type:Boolean})],ga.prototype,"interactive");var P0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.speed-rot-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 48px;
}

.turn-indicator,
.vessel-icon,
.speed-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
}

.turn-indicator {
  width: 24px;
  height: 12px;
}

.vessel-icon {
  width: 24px;
  height: 24px;
}

.speed-indicator {
  width: 16px;
  height: 12px;
}

.turn-indicator ::slotted(*),
.vessel-icon ::slotted(*),
.speed-indicator ::slotted(*) {
  width: 100%;
  height: 100%;
  color: inherit;
}
`;var R8=Object.defineProperty;var I8=Object.getOwnPropertyDescriptor;var z0=(e,t,i,o)=>{var r=o>1?void 0:o?I8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)R8(t,i,r);return r};var gs=class extends ga{constructor(){super(...arguments);this.type="regular"}get isSpeedRot(){return this.type==="speed-rot"}get baseType(){switch(this.type){case"indicator":return fo.Indicator;case"regular":return fo.Regular;case"large":case"speed-rot":return fo.Large;case"n-up":return fo.NUp;case"n-up-large":return fo.NUpLarge;default:return fo.Regular}}get icon(){if(this.isSpeedRot){return h`
        <div class="speed-rot-wrapper">
          <div class="turn-indicator">
            <slot name="turn-indicator"></slot>
          </div>
          <div class="vessel-icon">
            <slot></slot>
          </div>
          <div class="speed-indicator">
            <slot name="speed-indicator"></slot>
          </div>
        </div>
      `}return h`<slot></slot>`}};gs.styles=[...ga.styles,Q(P0)];z0([l({type:String})],gs.prototype,"type",2);gs=z0([x("obc-poi-object-vessel")],gs);var N8=Object.defineProperty;var j8=Object.getOwnPropertyDescriptor;var Ho=(e,t,i,o)=>{var r=o>1?void 0:o?j8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)N8(t,i,r);return r};var D1=(e=>{e["Tag"]="tag";e["Condensed"]="condensed";e["Regular"]="regular";e["Detailed"]="detailed";return e})(D1||{});var jr=class extends k{constructor(){super(...arguments);this.variant="regular";this.index="1";this.cardTitle="";this.description="";this.source="";this.timestamp="";this.hasLeadingIcon=false;this.hasCloseButton=false}get hasSource(){return this.source!==""}handleCloseClick(e){e.stopPropagation();this.dispatchEvent(new CustomEvent("close-click",{bubbles:true,composed:true}))}renderIndexBadge(){const e=this.variant==="tag";return h`
      <div class=${J({"index-badge":true,"tag-style":e})}>
        <span class="index-text">${this.index}</span>
      </div>
    `}renderSourceBadge(){if(!this.hasSource)return w;return h`
      <div class="source-badge">
        <span class="source-text">${this.source}</span>
      </div>
    `}renderTagVariant(){return h` <div class="tag-container">${this.renderIndexBadge()}</div> `}renderCondensedVariant(){return h`
      <div class="id-container">${this.renderIndexBadge()}</div>
      <div class="header-container">
        <span class="title condensed-title">${this.cardTitle}</span>
      </div>
      ${this.renderSourceBadge()}
    `}renderRegularVariant(){return h`
      <div class="id-container">${this.renderIndexBadge()}</div>
      <div class="header-container">
        ${this.hasLeadingIcon?h`<div class="icon-container">
              <slot class="leading-icon" name="leading-icon"></slot>
            </div>`:w}
        <span class="title">${this.cardTitle}</span>
      </div>
      ${this.renderSourceBadge()}
    `}renderDetailedVariant(){return h`
      <div class="id-container">${this.renderIndexBadge()}</div>
      <div class="detailed-content">
        <div class="poi-container">
          <obc-poi-object-vessel
            type="regular"
            .objectStyle=${"regular"}
            .state=${"static-unchecked"}
          >
            <slot name="poi-icon"></slot>
          </obc-poi-object-vessel>
        </div>
        <div class="text-container">
          <span class="title detailed-title">${this.cardTitle}</span>
          <span class="description">${this.description}</span>
        </div>
        <div class="meta-container">
          ${this.renderSourceBadge()}
          ${this.timestamp?h`<span class="timestamp">${this.timestamp}</span>`:w}
        </div>
      </div>
      ${this.hasCloseButton?h`<obc-icon-button
            variant="flat"
            class="close-button"
            @click=${this.handleCloseClick}
          >
            <obi-close-google></obi-close-google>
          </obc-icon-button>`:w}
    `}render(){return h`
      <div
        part="wrapper"
        class=${J({wrapper:true,[`variant-${this.variant}`]:true})}
      >
        ${this.variant==="tag"?this.renderTagVariant():this.variant==="condensed"?this.renderCondensedVariant():this.variant==="regular"?this.renderRegularVariant():this.renderDetailedVariant()}
      </div>
    `}};jr.styles=Q(A0);Ho([l({type:String})],jr.prototype,"variant",2);Ho([l({type:String})],jr.prototype,"index",2);Ho([l({type:String})],jr.prototype,"cardTitle",2);Ho([l({type:String})],jr.prototype,"description",2);Ho([l({type:String})],jr.prototype,"source",2);Ho([l({type:String})],jr.prototype,"timestamp",2);Ho([l({type:Boolean})],jr.prototype,"hasLeadingIcon",2);Ho([l({type:Boolean})],jr.prototype,"hasCloseButton",2);jr=Ho([x("obc-poi-card-header")],jr);var F8=Object.defineProperty;var U8=Object.getOwnPropertyDescriptor;var Jt=(e,t,i,o)=>{var r=o>1?void 0:o?U8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)F8(t,i,r);return r};var Ot=class extends k{constructor(){super(...arguments);this.pointerDirection="none";this.fixedSize=false;this.showHeader=true;this.headerVariant=D1.Condensed;this.index="1";this.cardTitle="";this.description="";this.source="";this.timestamp="";this.hasLeadingIcon=false;this.hasCloseButton=false;this.interactive=false;this.hasAlert=false}handleCardClick(){if(!this.interactive)return;this.dispatchEvent(new CustomEvent("card-click",{detail:{index:this.index},bubbles:true,composed:true}))}handleKeyDown(e){if(!this.interactive)return;if(e.target!==e.currentTarget)return;if(e.key===" "){e.preventDefault()}else if(e.key==="Enter"&&!e.repeat){e.preventDefault();this.handleCardClick()}}handleKeyUp(e){if(!this.interactive)return;if(e.target!==e.currentTarget)return;if(e.key===" "){e.preventDefault();this.handleCardClick()}}renderPointerSvg(e){const t={top:"M6 0L12 6H0L6 0Z",bottom:"M6 6L0 0H12L6 6Z",left:"M0 6L6 0V12L0 6Z",right:"M6 6L0 0V12L6 6Z"};const i=e==="top"||e==="bottom";const o=i?12:6;const r=i?6:12;return h`
      <svg
        width="${o}"
        height="${r}"
        viewBox="0 0 ${o} ${r}"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="${t[e]}"
          fill="var(--overlay-border-outline-color)"
        />
      </svg>
    `}renderTopPointer(){if(this.pointerDirection!=="top")return w;return h`
      <div class="pointer-container top">${this.renderPointerSvg("top")}</div>
    `}renderBottomPointer(){if(this.pointerDirection!=="bottom")return w;return h`
      <div class="pointer-container bottom">
        ${this.renderPointerSvg("bottom")}
      </div>
    `}renderLeftPointer(){if(this.pointerDirection!=="left")return w;return h`
      <div class="pointer-container left">${this.renderPointerSvg("left")}</div>
    `}renderRightPointer(){if(this.pointerDirection!=="right")return w;return h`
      <div class="pointer-container right">
        ${this.renderPointerSvg("right")}
      </div>
    `}renderHeader(){if(!this.showHeader)return w;return h`
      <obc-poi-card-header
        variant=${this.headerVariant}
        index=${this.index}
        cardTitle=${this.cardTitle}
        description=${this.description}
        source=${this.source}
        timestamp=${this.timestamp}
        ?hasLeadingIcon=${this.hasLeadingIcon}
        ?hasCloseButton=${this.hasCloseButton}
      >
        <slot name="leading-icon" slot="leading-icon"></slot>
        <slot name="poi-icon" slot="poi-icon"></slot>
      </obc-poi-card-header>
    `}renderAlertLayer(){if(!this.interactive||!this.hasAlert)return w;return h`
      <div class="alert-layer">
        <div class="ring-outer"></div>
        <div class="ring-middle alert"></div>
        <div class="ring-inner"></div>
      </div>
    `}render(){return h`
      <div
        class=${J({wrapper:true,"hug-content":!this.fixedSize,"fixed-size":this.fixedSize,interactive:this.interactive})}
      >
        ${this.renderTopPointer()}
        <div class="center">
          ${this.renderLeftPointer()}
          <div
            class="content-box"
            role=${this.interactive?"button":w}
            tabindex=${this.interactive?"0":w}
            aria-disabled=${this.interactive?"false":w}
            @click=${this.handleCardClick}
            @keydown=${this.handleKeyDown}
            @keyup=${this.handleKeyUp}
          >
            ${this.renderHeader()}
            <div class="content">
              <slot></slot>
            </div>
            ${this.renderAlertLayer()}
          </div>
          ${this.renderRightPointer()}
        </div>
        ${this.renderBottomPointer()}
      </div>
    `}};Ot.styles=Q(V0);Jt([l({type:String})],Ot.prototype,"pointerDirection",2);Jt([l({type:Boolean})],Ot.prototype,"fixedSize",2);Jt([l({type:Boolean,attribute:false})],Ot.prototype,"showHeader",2);Jt([l({type:String})],Ot.prototype,"headerVariant",2);Jt([l({type:String})],Ot.prototype,"index",2);Jt([l({type:String})],Ot.prototype,"cardTitle",2);Jt([l({type:String})],Ot.prototype,"description",2);Jt([l({type:String})],Ot.prototype,"source",2);Jt([l({type:String})],Ot.prototype,"timestamp",2);Jt([l({type:Boolean})],Ot.prototype,"hasLeadingIcon",2);Jt([l({type:Boolean})],Ot.prototype,"hasCloseButton",2);Jt([l({type:Boolean})],Ot.prototype,"interactive",2);Jt([l({type:Boolean})],Ot.prototype,"hasAlert",2);Ot=Jt([x("obc-poi-card")],Ot);var W8=Object.defineProperty;var G8=Object.getOwnPropertyDescriptor;var Vi=(e,t,i,o)=>{var r=o>1?void 0:o?G8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)W8(t,i,r);return r};var D0=180-45;var _i=qt;var B0=_i*Math.cos(D0*Math.PI/180);var O0=_i*Math.sin(D0*Math.PI/180);var So=class extends k{constructor(){super(...arguments);this.roll=0;this.minAvgRoll=0;this.maxAvgRoll=0;this.vesselImageFore=Er.psvFore;this.maxRollAdvice=void 0;this.triggerRollAdvice=false}render(){return h`
      <div class="container">
        <svg viewBox="-200 -200 400 400">
          <line
            x1="-${_i}"
            y1="0"
            x2="${_i}"
            y2="0"
            stroke="var(--instrument-frame-tertiary-color)"
          />
          <line
            x1="0"
            y1="0"
            y2="${_i-10}"
            x2="0"
            stroke="var(--instrument-enhanced-secondary-color)"
            transform="rotate(${this.roll} 0 0)"
          />
          <path
            d="M ${B0} ${O0} A ${_i} ${_i} 0 1 1 ${-B0} ${O0}"
            fill="none"
            stroke="var(--instrument-frame-tertiary-color)"
          />
        </svg>
        <obc-watch
          .watchCircleType=${Lr.double}
          tickmarksInside
          .areas=${[{startAngle:135,endAngle:225,roundOutsideCut:true,roundInsideCut:true}]}
          .barAreas=${[{startAngle:180+this.minAvgRoll,endAngle:180+this.maxAvgRoll,fillColor:"var(--instrument-enhanced-tertiary-color)"}]}
          .needles=${[{angle:180+this.roll,fillColor:"var(--instrument-enhanced-secondary-color)",strokeColor:"var(--border-silhouette-color)"}]}
          .vessels=${[{size:Dr.large,vesselImage:this.vesselImageFore,transform:`rotate(${this.roll}deg)`}]}
          .tickmarks=${[{angle:180,type:Te.main}]}
          .advices=${this.advices}
        ></obc-watch>
      </div>
    `}get advices(){const e=[];if(this.maxRollAdvice!==void 0){const t=this.triggerRollAdvice?de.triggered:de.regular;e.push({minAngle:135,maxAngle:180-this.maxRollAdvice,type:dt.caution,state:t,hideMinTickmark:true});e.push({minAngle:180+this.maxRollAdvice,maxAngle:225,type:dt.caution,state:t,hideMaxTickmark:true})}return e}};So.styles=L`
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
  `;Vi([l({type:Number})],So.prototype,"roll",2);Vi([l({type:Number})],So.prototype,"minAvgRoll",2);Vi([l({type:Number})],So.prototype,"maxAvgRoll",2);Vi([l({type:String})],So.prototype,"vesselImageFore",2);Vi([l({type:Number})],So.prototype,"maxRollAdvice",2);Vi([l({type:Boolean})],So.prototype,"triggerRollAdvice",2);So=Vi([x("obc-roll")],So);var q8=Object.defineProperty;var Y8=Object.getOwnPropertyDescriptor;var Fr=(e,t,i,o)=>{var r=o>1?void 0:o?Y8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)q8(t,i,r);return r};var cr=class extends qo(k){constructor(){super(...arguments);this.angle=0;this.variant="bar";this.maxAngle=90;this.showLabels=false;this.tickmarksInside=false;this.state=Le.active;this.priority=me.regular;this.tickmarkStyle=He.regular;this.advices=[];this.zoomToFitArc=false;this._radiusOffset=0}get _needleTransform(){const e=this._radiusOffset;if(e>0){return`translate(-256, -256) rotate(${-this.angle} 256 256) translate(0, ${e})`}return`translate(-256, -256) rotate(${-this.angle} 256 256)`}getAngle(e){return 180-e}get barColor(){if(this.variant==="needle"){if(this.state===Le.loading||this.state===Le.off){return"var(--instrument-frame-tertiary-color)"}return this.priority===me.enhanced?"var(--instrument-enhanced-tertiary-color)":"var(--instrument-regular-tertiary-color)"}else{if(this.state===Le.loading||this.state===Le.off){return"var(--instrument-frame-tertiary-color)"}return this.priority===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}}renderNeedle(){if(this.variant==="bar"){return w}let e;if(this.state===Le.loading||this.state===Le.off){e="var(--instrument-frame-tertiary-color)"}else{e=this.priority===me.enhanced?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)"}return c`
      <path
        transform="${this._needleTransform}"
        d="M260.462 411.447C259.81 416.73 251.933 416.645 251.514 411.191L239.826 259.24C239.618 258.192 239.508 257.109 239.508 256C239.508 255.764 239.514 255.528 239.524 255.294L239.503 255.039L239.462 254.5H239.576C240.334 246.09 247.401 239.5 256.008 239.5C264.615 239.5 271.681 246.09 272.439 254.5H272.542L272.5 255.039L272.488 255.196C272.501 255.462 272.508 255.731 272.508 256C272.508 257.144 272.391 258.261 272.169 259.339L260.487 411.191L260.462 411.447Z"
        fill="${e}"
        stroke="var(--border-silhouette-color)"
      />
    `}render(){const e=Math.max(2,this.maxAngle);const t=[{startAngle:180-e,endAngle:180+e,roundInsideCut:true,roundOutsideCut:true}];const i=[{startAngle:this.getAngle(0),endAngle:this.getAngle(this.angle),fillColor:this.barColor}];const o=this.setpoint!==void 0?180-this.setpoint:void 0;const r=[{angle:180,type:Te.primary,text:this.showLabels?"0":void 0},{angle:180,type:Te.zeroLineThick,color:this.barColor},{angle:180-e,type:Te.secondary,text:this.showLabels?e.toFixed(0):void 0},{angle:180+e,type:Te.secondary,text:this.showLabels?(-e).toFixed(0):void 0}];let a=null;if(e>70){a=45}else if(e>50){a=30}else if(e>40){a=22.5}if(a!==null){r.push({angle:180-a,type:Te.primary});r.push({angle:180+a,type:Te.primary})}const n=this.advices.map(d=>{const f=180-d.maxAngle;const g=180-d.minAngle;const m=this.setpoint!==void 0&&this.setpoint>=d.minAngle&&this.setpoint<=d.maxAngle;let u;if(m){u=de.triggered}else if(d.hinted){u=de.hinted}else{u=de.regular}return{minAngle:f,maxAngle:g,type:d.type,state:u}});let p;if(this.zoomToFitArc){const d=48;const f=(176+d)*2;const g=ml({areas:t,outerRadius:qt,innerRadius:w1(Lr.double),extension:d,targetSize:f});p=g.viewBox;this._radiusOffset=g.radiusOffset;this._arcFrame=g}else{p="-224 -44.8 448 268.8";this._radiusOffset=0;this._arcFrame=void 0}return h`
      <div class="container">
        <obc-watch
          .touching=${this.touching}
          .clipTop=${this.zoomToFitArc?0:40}
          .zoomToFitArc=${this.zoomToFitArc}
          .arcFrame=${this._arcFrame}
          .areas=${t}
          .angleSetpoint=${o}
          .newAngleSetpoint=${this.newSetpoint!==void 0?180-this.newSetpoint:void 0}
          .atAngleSetpoint=${this.computeAtSetpoint(this.angle)}
          .angleSetpointAtZeroDeadband=${this.setpointAtZeroDeadband}
          .setpointOverride=${this.setpointOverride}
          .animateSetpoint=${this.animateSetpoint}
          .padding=${48}
          .tickmarks=${r}
          .tickmarksInside=${this.tickmarksInside}
          .tickmarkStyle=${this.tickmarkStyle}
          .watchCircleType=${Lr.double}
          .barAreas=${i}
          .state=${this.state}
          .priority=${this.priority}
          .advices=${n}
        ></obc-watch>
        <svg viewBox="${p}">${this.renderNeedle()}</svg>
      </div>
    `}};cr.styles=L`
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
  `;Fr([l({type:Number})],cr.prototype,"angle",2);Fr([l({type:String})],cr.prototype,"variant",2);Fr([l({type:Number})],cr.prototype,"maxAngle",2);Fr([l({type:Boolean})],cr.prototype,"showLabels",2);Fr([l({type:Boolean})],cr.prototype,"tickmarksInside",2);Fr([l({type:String})],cr.prototype,"state",2);Fr([l({type:String})],cr.prototype,"priority",2);Fr([l({type:String})],cr.prototype,"tickmarkStyle",2);Fr([l({type:Array,attribute:false})],cr.prototype,"advices",2);Fr([l({type:Boolean})],cr.prototype,"zoomToFitArc",2);cr=Fr([x("obc-rudder")],cr);function Ai(e,t,i){if(t>=100){return null}const o=bi(i);const r=-t*e/100-2;return c`<line x1="12" x2="32" y1=${r}  y2=${r} stroke=${o} stroke-width="1" vector-effect="non-scaling-stroke"/>`}function E1(e,t,i,o,r){const a=8;const n=12;const p=n+a;const d=a/2;const f=-t*e/100-2*d-2;const g=-i*e/100+2*d-2;const m=`M ${n} ${f} 
                    A ${d} ${d} 0 0 0 ${p} ${f}
                    V ${g}
                    A ${d} ${d} 0 0 0 ${n} ${g}
                    Z`;return c`<path d=${m} fill=${o} stroke=${r} stroke-width="1" vector-effect="non-scaling-stroke" />`}function E0(e,t,i){if(t.type===dt.caution){let o;let r=null;if(t.state===de.hinted){o="var(--instrument-frame-tertiary-color)"}else if(t.state===de.regular){o="var(--instrument-tick-mark-tertiary-color)"}else{o="var(--on-caution-active-color)";r="var(--alert-caution-color)"}const a=[];const n=i?50:-50;for(let f=-100;f<300;f+=16){a.push(c`<g transform="translate(0 ${-f}) ">
            <path d="M 50 0 L 0 ${n}" stroke=${o} stroke-width="6"/>
            </g>
            `)}const p=`adviceMask-${t.min}-${t.max}`;let d=He.regular;if(t.state===de.regular){d=He.regular}else if(t.state===de.triggered){d=He.enhanced}return c`
            <mask id=${p}>
                ${E1(e,t.min,t.max,"white","black")}
            </mask>
            <g mask="url(#${p})">
                ${r?c`<rect x="-256" y="-512" width="512" height="1024" fill="${r}"/>`:w}
                ${a}
            </g>
            ${E1(e,t.min,t.max,"none",o)}
            ${Ai(e,t.min,d)}
            ${Ai(e,t.max,d)}
        `}else{let o;let r;let a;if(t.state===de.hinted){o="var(--instrument-frame-tertiary-color)";a="none";r=He.regular}else if(t.state===de.regular){o="var(--instrument-regular-secondary-color)";a="none";r=He.regular}else{o="var(--instrument-enhanced-secondary-color)";a=o;r=He.regular}return c`
            ${E1(e,t.min,t.max,a,o)}
            ${Ai(e,t.min,r)}
            ${Ai(e,t.max,r)}
        `}}var hn=(e=>{e["none"]="none";e["cap"]="cap";e["single"]="single";return e})(hn||{});function Q8(e,t){const i=-e-22;return c`
  <path transform="translate(-15 ${i})" d="M0.707007 14.2929L14.9999 0L29.2928 14.2929C29.9228 14.9229 29.4766 16 28.5857 16H1.41412C0.523211 16 0.0770419 14.9229 0.707007 14.2929Z" fill=${t}/>`}function R0(e,t,i){if(i==="none"){return Q8(e,t)}else if(i==="cap"){const o=-e-50-1;return c`
        <g transform="translate(-80 ${o})">
        <path d="M60.0016 49L60.001 37.0005C60.0004 25.9547 68.9547 17 80.0005 17C91.0459 17 100 25.9541 100 36.9995V49H60.0016Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke"/>
        <path d="M90.3784 10.889L79.9991 1.00391L69.6198 10.889C68.3125 12.1341 69.1937 14.3372 70.9991 14.3372H88.9991C90.8046 14.3372 91.6858 12.1341 90.3784 10.889Z" fill=${t} stroke-linecap="square"/>
        </g>`}else if(i==="single"){const o=-e-50-1;return c`
        <g transform="translate(-80 ${o})">
<path d="M60.0016 49L60.0016 23C60.0007 19.6866 62.6865 17 66 17L94 17C97.3137 17 100 19.6863 100 23L100 49L60.0016 49Z" fill="var(--instrument-frame-primary-color)" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
<path d="M9 33.2643C9.00007 42.0397 60.2667 45 60.2667 45C60.2667 37.2905 62.8316 29.87 67.4405 24.2456L70.1 21C56.8343 21 8.99993 24.489 9 33.2643Z" fill="var(--instrument-frame-primary-color)"  stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
<path d="M151 32.7357C151 23.9604 99.7333 21 99.7333 21C99.7333 28.7095 97.1684 36.1301 92.5595 41.7544L89.9 45C103.166 45 151 41.511 151 32.7357Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke"/>
<path d="M90.3784 10.889L79.9991 1.00391L69.6198 10.889C68.3125 12.1341 69.1937 14.3372 70.9991 14.3372H88.9991C90.8046 14.3372 91.6858 12.1341 90.3784 10.889Z" fill=${t} stroke-linecap="square" vector-effect="non-scaling-stroke"/>
</g>
`}else{return null}}function I0(e,t){if(t==="none"){return null}else if(t==="cap"){const i=e+1;return c`
        <g transform="translate(-80 ${i})">
<path d="M60.0016 1C60.0006 17.7823 67.4013 33.9132 80 45C92.5988 33.9131 100 17.7824 100 1L60.0016 1Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke"/>
</g>`}else if(t==="single"){const i=e+1;return c`
        <g transform="translate(-80 ${i})">
        <svg width="160" height="49" viewBox="0 0 160 49" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M60.0016 1C60.0006 17.7823 67.4013 33.9132 80 45C92.5988 33.9131 100 17.7824 100 1L60.0016 1Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" />
<path d="M151 16.7357C151 7.96035 99.7333 5 99.7333 5C98.5 13.5 92 24 81.9 29C95.1657 29 151 25.511 151 16.7357Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" />
<path d="M9 17.2643C9.00007 26.0397 67.2667 29 67.2667 29C63.5 22 69.5 8.5 82.1 5C68.8343 5 8.99993 8.48898 9 17.2643Z" stroke="var(--instrument-frame-tertiary-color)" fill="var(--instrument-frame-primary-color)" vector-effect="non-scaling-stroke" />
</g>`}else{return null}}var K8=Object.defineProperty;var X8=Object.getOwnPropertyDescriptor;var Ur=(e,t,i,o)=>{var r=o>1?void 0:o?X8(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)K8(t,i,r);return r};var dr=class extends qo(k,{defaultDeadband:1}){constructor(){super(...arguments);this._setpointId=`thruster-sp-${Math.random().toString(36).slice(2,9)}`;this.thrust=0;this.state=Le.active;this.priority=me.regular;this.tunnel=false;this.singleSided=false;this.singleDirection=false;this.singleDirectionHalfSize=false;this.advices=[];this.topPropeller=hn.none;this.bottomPropeller=hn.none}render(){return h`<div class="container">
      ${a3(this.thrust,this.setpoint,this.state,this.priority,{atSetpoint:this.atSetpoint,tunnel:this.tunnel,setpointAtZeroDeadband:this.setpointAtZeroDeadband,autoAtSetpoint:this.autoAtSetpoint,autoAtSetpointDeadband:this.autoAtSetpointDeadband,touching:this.touching,singleSided:this.singleSided,advices:this.advices,singleDirection:this.singleDirection,singleDirectionHalfSize:this.singleDirectionHalfSize,topPropeller:this.topPropeller,bottomPropeller:this.bottomPropeller,narrow:!this.tunnel,newSetpoint:this.newSetpoint,setpointId:this._setpointId})}
    </div>`}};dr.styles=L`
    .container {
      height: 100%;
      width: 100%;
    }

    .container > svg {
      height: 100%;
      width: 100%;
    }
  `;Ur([l({type:Number})],dr.prototype,"thrust",2);Ur([l({type:String})],dr.prototype,"state",2);Ur([l({type:String})],dr.prototype,"priority",2);Ur([l({type:Boolean})],dr.prototype,"tunnel",2);Ur([l({type:Boolean})],dr.prototype,"singleSided",2);Ur([l({type:Boolean})],dr.prototype,"singleDirection",2);Ur([l({type:Boolean})],dr.prototype,"singleDirectionHalfSize",2);Ur([l({type:Array})],dr.prototype,"advices",2);Ur([l({type:String})],dr.prototype,"topPropeller",2);Ur([l({type:String})],dr.prototype,"bottomPropeller",2);dr=Ur([x("obc-thruster")],dr);function F0(e,t,i,o){const r=c`
      <path transform="translate(0 -2)" d="M -44 0  v -${e-8}  a 8 8 0 0 1 8 -8 h 72 a 8 8 0 0 1 8 8 V 0 Z" fill=${i.container} stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
  `;const a=o.off?null:c`<rect width="40" height=${e} x="-20" y=${-2-e} fill="var(--instrument-frame-secondary-color)" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>`;const n=[];const p=2;const d=e/p;if(!o.hideTicks){for(let u=1;u<p;u++){n.push(c`<line x1="-24" x2="-44" y1=${-u*d-2}  y2=${-u*d-2} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`);n.push(c`<line  x1="24"  x2="44" y1=${-u*d-2}  y2=${-u*d-2} stroke="var(--instrument-frame-tertiary-color)" stroke-width="1" vector-effect="non-scaling-stroke"/>`)}}const f=e*t/100;const g=-2-f;const m=c`<rect width="40" height=${f} x="-20" y=${g} fill=${i.box} stroke=${i.box} vector-effect="non-scaling-stroke"/>`;if(o.hideContainer){return[a,n,m]}else{return[r,a,n,m]}}function U0(e,t,i,o,r){const a=o.narrow?c`
      <path transform="translate(0 -2)" d="M -32 0  v -${e-8}  a 8 8 0 0 1 8 -8 h 48 a 8 8 0 0 1 8 8 V 0 Z" fill=${i.container} stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
  `:c`
      <path transform="translate(0 -2)" d="M -40 0  v -${e-8}  a 8 8 0 0 1 8 -8 h 56 a 8 8 0 0 1 8 8 V 0 Z" fill=${i.container} stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
  `;let n=o.narrow?c`
      <path transform="translate(0 -2)" d="M -32 0  v -${e-8}  a 8 8 0 0 1 8 -8 h 32 V 0 Z" fill="var(--instrument-frame-secondary-color)" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
  `:c`
      <path transform="translate(0 -2)" d="M -40 0  v -${e-8}  a 8 8 0 0 1 8 -8 h 40 V 0 Z" fill="var(--instrument-frame-secondary-color)" stroke="var(--instrument-frame-tertiary-color)" vector-effect="non-scaling-stroke"/>
  `;if(o.off){n=null}const p=o.hideTicks?[]:[Ai(e,50,He.regular)];const d=e*t/100;const f=o.narrow?40:48;const g=o.narrow?-32:-40;const m=-2-d;const u=o.flipAdicePattern?"thrusterBarMask1":"thrusterBarMask2";const M=o.hideContainer?w:c`
  <defs>
  <mask id=${u}>
  <path transform="translate(0 -2)" d="M ${g} 0  v -${e-8}  a 8 8 0 0 1 8 -8 h ${f} V 0 Z" fill="white" stroke="white" vector-effect="non-scaling-stroke"/>
  </defs>`;const C=o.hideContainer?void 0:`url(#${u})`;const A=c`
    ${M}
    <rect mask=${C} width=${f} height=${d} x=${g} y=${m} fill=${i.box} stroke=${i.box} vector-effect="non-scaling-stroke"/>`;const H=r.map(S=>E0(e,S,o.flipAdicePattern));const _=[p,A,H];if(!o.hideContainer){_.splice(0,0,[a,n])}if(!o.narrow){return c`<g transform="translate(4 0)">${_}</g>`}else{return _}}function J8(e,t,i,o){const r=c`
      <g transform="rotate(180)">
        ${F0(e,t,i,o)}
      </g>
  `;return r}function e3(e,t,i,o,r){const a=c`
      <g transform="rotate(180) scale(-1,1)">
        ${U0(e,t,i,{hideTicks:o.hideTicks,flipAdicePattern:o.flipAdicePattern,hideContainer:o.hideContainer,narrow:o.narrow,off:o.off},r)}
      </g>
  `;return a}var N0=4;function j0(e,t,i){return-(i?0:Math.sign(t)*(e*Math.abs(t)/100+2))}function t3(e){const t=e.state===Le.loading||e.state===Le.off;const i=t&&!e.setpointOverride;const o=e.priority===me.enhanced?gi.enhanced:gi.regular;if(t){return{visualState:at.notEqual,colorMode:o,disabled:i}}if(e.touching&&!e.hasNewSetpoint){return{visualState:at.focus,colorMode:o,disabled:false}}if(e.atSetpoint&&e.setpointAtZero){return{visualState:at.equalZero,colorMode:o,disabled:false}}if(e.atSetpoint){return{visualState:at.equal,colorMode:o,disabled:false}}return{visualState:at.notEqual,colorMode:o,disabled:false}}function r3(e,t,i){const o=Math.abs(t)<i.setpointAtZeroDeadband;const r=i.newSetpoint!==void 0;const a=i.departingNewSetpoint!==void 0;const n=i.animateSetpoint===true;const{visualState:p,colorMode:d,disabled:f}=t3({state:i.state,priority:i.priority,atSetpoint:i.atSetpoint,touching:i.touching,setpointAtZero:o,hasNewSetpoint:r,setpointOverride:i.setpointOverride});const g=j0(e,t,o);const m=28+(i.singleSided?-12:0)+(i.narrow?0:4);const u=No(p);const M=m+u-N0;const C=r?.75:1;const A=nr({visualState:p,colorMode:d,disabled:f,id:`${i.id}-r`});const H=[];if(n){const _=`var(${io}, ${ko})`;H.push(c`<g style="transform: translate(${M}px, ${g}px) rotate(90deg); opacity: ${C}; transition: transform ${_} ease-out, opacity ${_} ease-out;">${A}</g>`);if(!i.singleSided){const S=nr({visualState:p,colorMode:d,disabled:f,id:`${i.id}-l`});H.push(c`<g style="transform: translate(${-M}px, ${g}px) rotate(-90deg); opacity: ${C}; transition: transform ${_} ease-out, opacity ${_} ease-out;">${S}</g>`)}}else{H.push(c`<g transform="translate(${M}, ${g}) rotate(90)" opacity="${C}">${A}</g>`);if(!i.singleSided){const _=nr({visualState:p,colorMode:d,disabled:f,id:`${i.id}-l`});H.push(c`<g transform="translate(${-M}, ${g}) rotate(-90)" opacity="${C}">${_}</g>`)}}if(r||a){const _=r;const S=_?i.newSetpoint:i.departingNewSetpoint;const E=Math.abs(S)<i.setpointAtZeroDeadband;const D=j0(e,S,E);const K=No(at.focus);const I=m+K-N0;const Y=_?1:0;const R=nr({visualState:at.focus,colorMode:d,disabled:false,id:`${i.id}-nr`});if(n){const B=`var(${io}, ${ko})`;H.push(c`<g style="transform: translate(${I}px, ${D}px) rotate(90deg); opacity: ${Y}; transition: opacity ${B} ease-out;">${R}</g>`);if(!i.singleSided){const F=nr({visualState:at.focus,colorMode:d,disabled:false,id:`${i.id}-nl`});H.push(c`<g style="transform: translate(${-I}px, ${D}px) rotate(-90deg); opacity: ${Y}; transition: opacity ${B} ease-out;">${F}</g>`)}}else{H.push(c`<g transform="translate(${I}, ${D}) rotate(90)" opacity="${Y}">${R}</g>`);if(!i.singleSided){const B=nr({visualState:at.focus,colorMode:d,disabled:false,id:`${i.id}-nl`});H.push(c`<g transform="translate(${-I}, ${D}) rotate(-90)" opacity="${Y}">${B}</g>`)}}}return c`${H}`}function o3(e,t,i,o,r){const a=-(i?0:Math.sign(t)*(e*Math.abs(t)/100+2));const n=(r.singleSided?-12:0)+(r.narrow?0:4);let p;if(r.filled){p="M23.5119 8C24.6981 6.35191 23.5696 4 21.5926 4L2.39959 4C0.422598 4 -0.705911 6.35191 0.480283 8L11.9961 24L23.5119 8Z"}else{p="M18.5836 8L5.4086 8L11.9961 17.1526L18.5836 8ZM23.5119 8C24.6981 6.35191 23.5696 4 21.5926 4L2.39959 4C0.422598 4 -0.705911 6.35191 0.480283 8L11.9961 24L23.5119 8Z"}return c`
    <defs>
      <g id="thrusterSetpoint">
        <path fill-rule="evenodd" clip-rule="evenodd" transform="translate(24 -12) rotate(90)" d=${p} vector-effect="non-scaling-stroke"/>
      </g>
      <mask id="thrusterSetpointMask">
        <rect x="-20" y="-20" width="50" height="50" fill="white" />
        <use href="#thrusterSetpoint" fill="black" />
      </mask>
    </defs>
  <g transform="translate(0 ${a})">
    <use href="#thrusterSetpoint" fill=${o.fill} stroke="none" transform="translate(${28+n} 0)"/>
    <use href="#thrusterSetpoint" mask="url(#thrusterSetpointMask)" transform="translate(${28+n} 0)" fill="none" stroke=${o.stroke} stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    ${r.singleSided?null:c`
    <use href="#thrusterSetpoint" transform="rotate(180) translate(28 0)" fill=${o.fill} stroke="none"/>
    <use href="#thrusterSetpoint" transform="rotate(180) translate(28 0)" mask="url(#thrusterSetpointMask)" fill="none" stroke=${o.stroke} stroke-width="2" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
      `}
  </g>
  `}function i3(e,t,i){if(i.touching){return false}if(i.autoAtSetpoint&&t!==void 0){return Math.abs(e-t)<i.autoAtSetpointDeadband}return i.atSetpoint}function a3(e,t,i,o,r){if(r.tunnel){e=-e;t=t===void 0?void 0:-t}if(!r.singleSided&&r.advices.length>0){throw new Error("Double sided thruster does not support advice")}r.atSetpoint=i3(e,t,r);const a=l3(r,i,o);let n=c`
    <rect x="-44" y="-2" width="88" height="4" stroke-width="1" fill=${a.zeroLineColor} stroke=${a.zeroLineColor} vector-effect="non-scaling-stroke"/>
  `;if(r.singleSided){const M=r.narrow?64:72;const C=r.narrow?-32:-36;n=c`<rect x=${C} y="-2" width=${M} height="4" stroke-width="1" fill=${a.zeroLineColor} stroke=${a.zeroLineColor} vector-effect="non-scaling-stroke"/>`}const p=Math.abs(t||0)<r.setpointAtZeroDeadband;const{topAdvices:d,bottomAdvices:f}=n3(r.advices,t);const g=[];const m=r.topPropeller===hn.none?134:106;const u=r.singleDirection?m*2:m;if(r.singleSided){g.push(U0(u,Math.max(e,0),{box:a.boxColor,container:a.containerBackgroundColor},{hideTicks:a.hideTicks,flipAdicePattern:false,hideContainer:false,narrow:r.narrow,off:i===Le.off},d));if(!(r.singleDirection||r.singleDirectionHalfSize)){g.push(e3(u,Math.max(-e,0),{box:a.boxColor,container:a.containerBackgroundColor},{hideTicks:a.hideTicks,flipAdicePattern:true,hideContainer:false,narrow:r.narrow,off:i===Le.off},f))}g.push(n)}else{g.push(F0(u,Math.max(e,0),{box:a.boxColor,container:a.containerBackgroundColor},{hideTicks:a.hideTicks,hideContainer:false,off:i===Le.off}));if(!r.singleDirection){g.push(J8(u,Math.max(-e,0),{box:a.boxColor,container:a.containerBackgroundColor},{hideTicks:a.hideTicks,hideContainer:false,off:i===Le.off}))}g.push(n)}if(t!==void 0){if(r.setpointId){g.push(r3(u,t,{state:i,priority:o,atSetpoint:r.atSetpoint,touching:r.touching,setpointAtZeroDeadband:r.setpointAtZeroDeadband,singleSided:r.singleSided,narrow:r.narrow,newSetpoint:r.newSetpoint,id:r.setpointId,animateSetpoint:r.animateSetpoint,departingNewSetpoint:r.departingNewSetpoint,setpointOverride:r.setpointOverride}))}else{g.push(o3(u,t,p,{fill:a.setPointColor,stroke:"var(--border-silhouette-color)"},{filled:o===me.enhanced||i===Le.off,singleSided:r.singleSided,narrow:r.narrow}))}}if(r.tunnel){return c`
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="-160 -64  320 128" x="-160" y="-64">
        <g transform="rotate(-90)">
          ${g}
        </g>
      </svg>`}else{let M="-80 -160 160 320";let C=-160;if(r.singleDirection){M="-80 -300 160 320";C=-320}const A=R0(u,a.arrowColor,r.topPropeller);const H=I0(r.singleDirectionHalfSize?.5:u,r.bottomPropeller);return c`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox=${M} x="-80" y=${C} width="160" height="320">
      ${A}
      ${H}
      ${g}
    </svg>
  `}}function n3(e,t){const i=e.map(a=>{const n=t!==void 0&&t>=a.min&&t<=a.max;let p;if(n){p=de.triggered}else if(a.hinted){p=de.hinted}else{p=de.regular}return{min:a.min,max:a.max,type:a.type,state:p,hinted:a.hinted}});const o=i.filter(a=>a.min>=0);const r=i.filter(a=>a.max<=0).map(a=>({...a,min:-a.max,max:-a.min}));return{topAdvices:o,bottomAdvices:r}}function l3(e,t,i){const o=i===me.enhanced;let r=o?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";let a=o?"var(--instrument-enhanced-primary-color)":"var(--instrument-regular-primary-color)";let n="var(--instrument-regular-secondary-color)";let p="var(--instrument-frame-primary-color)";let d=o?"var(--instrument-enhanced-secondary-color)":"var(--instrument-regular-secondary-color)";let f=false;if(e.atSetpoint){a=r}if(t===Le.loading){r="transparent";a="var(--instrument-frame-tertiary-color)";d="var(--instrument-frame-tertiary-color)";n="var(--instrument-regular-secondary-color)";f=true}else if(t===Le.off){r="transparent";a="var(--instrument-frame-tertiary-color)";n="var(--instrument-frame-tertiary-color)";d="var(--instrument-frame-tertiary-color)";f=true;p="transparent"}return{zeroLineColor:d,boxColor:r,containerBackgroundColor:p,hideTicks:f,setPointColor:a,arrowColor:n}}var W0=L`
          * {
            -webkit-tap-highlight-color: transparent;
          }

.chart-container {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

#chart {
  position: relative;
  width: 32px;
  height: 32px;
  background: var(--instrument-frame-primary-color);
  border-radius: 4px;
  border: 1px solid var(--instrument-frame-tertiary-color);
}

#chart canvas {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
}

#dot {
  position: absolute;
  width: 4px;
  height: 4px;
  right: -3px;
  border-radius: 50%;
  background: var(--element-neutral-color);
  border: 1px solid var(--border-silhouette-color);
}
`;var s3=true;var vt="u-";var c3="uplot";var d3=vt+"hz";var p3=vt+"vt";var h3=vt+"title";var u3=vt+"wrap";var f3=vt+"under";var v3=vt+"over";var m3=vt+"axis";var Pi=vt+"off";var g3=vt+"select";var b3=vt+"cursor-x";var y3=vt+"cursor-y";var w3=vt+"cursor-pt";var C3=vt+"legend";var k3=vt+"live";var L3=vt+"inline";var x3=vt+"series";var $3=vt+"marker";var G0=vt+"label";var M3=vt+"value";var vn="width";var mn="height";var un="top";var q0="bottom";var ba="left";var R1="right";var oc="#000";var Y0=oc+"0";var I1="mousemove";var Q0="mousedown";var N1="mouseup";var K0="mouseenter";var X0="mouseleave";var J0="dblclick";var H3="resize";var S3="scroll";var e5="change";var ks="dppxchange";var ic="--";var $a=typeof window!="undefined";var G1=$a?document:null;var wa=$a?window:null;var _3=$a?navigator:null;var De;var bs;function q1(){let e=devicePixelRatio;if(De!=e){De=e;bs&&Q1(e5,bs,q1);bs=matchMedia(`(min-resolution: ${De-.001}dppx) and (max-resolution: ${De+.001}dppx)`);zi(e5,bs,q1);wa.dispatchEvent(new CustomEvent(ks))}}function pr(e,t){if(t!=null){let i=e.classList;!i.contains(t)&&i.add(t)}}function Y1(e,t){let i=e.classList;i.contains(t)&&i.remove(t)}function Je(e,t,i){e.style[t]=i+"px"}function Wr(e,t,i,o){let r=G1.createElement(e);if(t!=null)pr(r,t);if(i!=null)i.insertBefore(r,o);return r}function Vr(e,t){return Wr("div",e,t)}var t5=new WeakMap;function vo(e,t,i,o,r){let a="translate("+t+"px,"+i+"px)";let n=t5.get(e);if(a!=n){e.style.transform=a;t5.set(e,a);if(t<0||i<0||t>o||i>r)pr(e,Pi);else Y1(e,Pi)}}var r5=new WeakMap;function o5(e,t,i){let o=t+i;let r=r5.get(e);if(o!=r){r5.set(e,o);e.style.background=t;e.style.borderColor=i}}var i5=new WeakMap;function a5(e,t,i,o){let r=t+""+i;let a=i5.get(e);if(r!=a){i5.set(e,r);e.style.height=i+"px";e.style.width=t+"px";e.style.marginLeft=o?-t/2+"px":0;e.style.marginTop=o?-i/2+"px":0}}var ac={passive:true};var V3={...ac,capture:true};function zi(e,t,i,o){t.addEventListener(e,i,o?V3:ac)}function Q1(e,t,i,o){t.removeEventListener(e,i,ac)}$a&&q1();function Gr(e,t,i,o){let r;i=i||0;o=o||t.length-1;let a=o<=2147483647;while(o-i>1){r=a?i+o>>1:hr((i+o)/2);if(t[r]<e)i=r;else o=r}if(e-t[i]<=t[o]-e)return i;return o}function T5(e){let t=(i,o,r)=>{let a=-1;let n=-1;for(let p=o;p<=r;p++){if(e(i[p])){a=p;break}}for(let p=r;p>=o;p--){if(e(i[p])){n=p;break}}return[a,n]};return t}var P5=e=>e!=null;var z5=e=>e!=null&&e>0;var $s=T5(P5);var A3=T5(z5);function Z3(e,t,i,o=0,r=false){let a=r?A3:$s;let n=r?z5:P5;[t,i]=a(e,t,i);let p=e[t];let d=e[t];if(t>-1){if(o==1){p=e[t];d=e[i]}else if(o==-1){p=e[i];d=e[t]}else{for(let f=t;f<=i;f++){let g=e[f];if(n(g)){if(g<p)p=g;else if(g>d)d=g}}}}return[p??Ge,d??-Ge]}function Ms(e,t,i,o){let r=s5(e);let a=s5(t);if(e==t){if(r==-1){e*=i;t/=i}else{e/=i;t*=i}}let n=i==10?_o:B5;let p=r==1?hr:Ar;let d=a==1?Ar:hr;let f=p(n(ft(e)));let g=d(n(ft(t)));let m=Ca(i,f);let u=Ca(i,g);if(i==10){if(f<0)m=qe(m,-f);if(g<0)u=qe(u,-g)}if(o||i==2){e=m*r;t=u*a}else{e=R5(e,m);t=Hs(t,u)}return[e,t]}function nc(e,t,i,o){let r=Ms(e,t,i,o);if(e==0)r[0]=0;if(t==0)r[1]=0;return r}var lc=.1;var n5={mode:3,pad:lc};var bn={pad:0,soft:null,mode:0};var T3={min:bn,max:bn};function Ls(e,t,i,o){if(Ss(i))return l5(e,t,i);bn.pad=i;bn.soft=o?0:null;bn.mode=o?3:0;return l5(e,t,T3)}function Pe(e,t){return e==null?t:e}function P3(e,t,i){t=Pe(t,0);i=Pe(i,e.length-1);while(t<=i){if(e[t]!=null)return true;t++}return false}function l5(e,t,i){let o=i.min;let r=i.max;let a=Pe(o.pad,0);let n=Pe(r.pad,0);let p=Pe(o.hard,-Ge);let d=Pe(r.hard,Ge);let f=Pe(o.soft,Ge);let g=Pe(r.soft,-Ge);let m=Pe(o.mode,0);let u=Pe(r.mode,0);let M=t-e;let C=_o(M);let A=Ut(ft(e),ft(t));let H=_o(A);let _=ft(H-C);if(M<1e-24||_>10){M=0;if(e==0||t==0){M=1e-24;if(m==2&&f!=Ge)a=0;if(u==2&&g!=-Ge)n=0}}let S=M||A||1e3;let E=_o(S);let D=Ca(10,hr(E));let K=S*(M==0?e==0?.1:1:a);let I=qe(R5(e-K,D/10),24);let Y=e>=f&&(m==1||m==3&&I<=f||m==2&&I>=f)?f:Ge;let R=Ut(p,I<Y&&e>=Y?Y:qr(Y,I));let B=S*(M==0?t==0?.1:1:n);let F=qe(Hs(t+B,D/10),24);let z=t<=g&&(u==1||u==3&&F>=g||u==2&&F<=g)?g:-Ge;let ee=qr(d,F>z&&t<=z?z:Ut(z,F));if(R==ee&&R==0)ee=100;return[R,ee]}var z3=new Intl.NumberFormat($a?_3.language:"en-US");var sc=e=>z3.format(e);var ur=Math;var Cs=ur.PI;var ft=ur.abs;var hr=ur.floor;var ut=ur.round;var Ar=ur.ceil;var qr=ur.min;var Ut=ur.max;var Ca=ur.pow;var s5=ur.sign;var _o=ur.log10;var B5=ur.log2;var B3=(e,t=1)=>ur.sinh(e)*t;var j1=(e,t=1)=>ur.asinh(e/t);var Ge=Infinity;function c5(e){return(_o((e^e>>31)-(e>>31))|0)+1}function K1(e,t,i){return qr(Ut(e,t),i)}function O5(e){return typeof e=="function"}function _e(e){return O5(e)?e:()=>e}var O3=()=>{};var D5=e=>e;var E5=(e,t)=>t;var D3=e=>null;var d5=e=>true;var p5=(e,t)=>e==t;var E3=/\.\d*?(?=9{6,}|0{6,})/gm;var Bi=e=>{if(N5(e)||Jo.has(e))return e;const t=`${e}`;const i=t.match(E3);if(i==null)return e;let o=i[0].length-1;if(t.indexOf("e-")!=-1){let[r,a]=t.split("e");return+`${Bi(r)}e${a}`}return qe(e,o)};function Zi(e,t){return Bi(qe(Bi(e/t))*t)}function Hs(e,t){return Bi(Ar(Bi(e/t))*t)}function R5(e,t){return Bi(hr(Bi(e/t))*t)}function qe(e,t=0){if(N5(e))return e;let i=10**t;let o=e*i*(1+Number.EPSILON);return ut(o)/i}var Jo=new Map;function I5(e){return((""+e).split(".")[1]||"").length}function wn(e,t,i,o){let r=[];let a=o.map(I5);for(let n=t;n<i;n++){let p=ft(n);let d=qe(Ca(e,n),p);for(let f=0;f<o.length;f++){let g=e==10?+`${o[f]}e${n}`:o[f]*d;let m=(n>=0?0:p)+(n>=a[f]?0:a[f]);let u=e==10?g:qe(g,m);r.push(u);Jo.set(u,m)}}return r}var yn={};var cc=[];var ka=[null,null];var Xo=Array.isArray;var N5=Number.isInteger;var R3=e=>e===void 0;function h5(e){return typeof e=="string"}function Ss(e){let t=false;if(e!=null){let i=e.constructor;t=i==null||i==Object}return t}function I3(e){return e!=null&&typeof e=="object"}var N3=Object.getPrototypeOf(Uint8Array);var j5="__proto__";function La(e,t=Ss){let i;if(Xo(e)){let o=e.find(r=>r!=null);if(Xo(o)||t(o)){i=Array(e.length);for(let r=0;r<e.length;r++)i[r]=La(e[r],t)}else i=e.slice()}else if(e instanceof N3)i=e.slice();else if(t(e)){i={};for(let o in e){if(o!=j5)i[o]=La(e[o],t)}}else i=e;return i}function lt(e){let t=arguments;for(let i=1;i<t.length;i++){let o=t[i];for(let r in o){if(r!=j5){if(Ss(e[r]))lt(e[r],La(o[r]));else e[r]=La(o[r])}}}return e}var j3=0;var F3=1;var U3=2;function W3(e,t,i){for(let o=0,r,a=-1;o<t.length;o++){let n=t[o];if(n>a){r=n-1;while(r>=0&&e[r]==null)e[r--]=null;r=n+1;while(r<i&&e[r]==null)e[a=r++]=null}}}function G3(e,t){if(Q3(e)){let n=e[0].slice();for(let p=1;p<e.length;p++)n.push(...e[p].slice(1));if(!K3(n[0]))n=Y3(n);return n}let i=new Set;for(let n=0;n<e.length;n++){let p=e[n];let d=p[0];let f=d.length;for(let g=0;g<f;g++)i.add(d[g])}let o=[Array.from(i).sort((n,p)=>n-p)];let r=o[0].length;let a=new Map;for(let n=0;n<r;n++)a.set(o[0][n],n);for(let n=0;n<e.length;n++){let p=e[n];let d=p[0];for(let f=1;f<p.length;f++){let g=p[f];let m=Array(r).fill(void 0);let u=t?t[n][f]:F3;let M=[];for(let C=0;C<g.length;C++){let A=g[C];let H=a.get(d[C]);if(A===null){if(u!=j3){m[H]=A;if(u==U3)M.push(H)}}else m[H]=A}W3(m,M,r);o.push(m)}}return o}var q3=typeof queueMicrotask=="undefined"?e=>Promise.resolve().then(e):queueMicrotask;function Y3(e){let t=e[0];let i=t.length;let o=Array(i);for(let a=0;a<o.length;a++)o[a]=a;o.sort((a,n)=>t[a]-t[n]);let r=[];for(let a=0;a<e.length;a++){let n=e[a];let p=Array(i);for(let d=0;d<i;d++)p[d]=n[o[d]];r.push(p)}return r}function Q3(e){let t=e[0][0];let i=t.length;for(let o=1;o<e.length;o++){let r=e[o][0];if(r.length!=i)return false;if(r!=t){for(let a=0;a<i;a++){if(r[a]!=t[a])return false}}}return true}function K3(e,t=100){const i=e.length;if(i<=1)return true;let o=0;let r=i-1;while(o<=r&&e[o]==null)o++;while(r>=o&&e[r]==null)r--;if(r<=o)return true;const a=Ut(1,hr((r-o+1)/t));for(let n=e[o],p=o+a;p<=r;p+=a){const d=e[p];if(d!=null){if(d<=n)return false;n=d}}return true}var F5=["January","February","March","April","May","June","July","August","September","October","November","December"];var U5=["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];function W5(e){return e.slice(0,3)}var X3=U5.map(W5);var J3=F5.map(W5);var e6={MMMM:F5,MMM:J3,WWWW:U5,WWW:X3};function fn(e){return(e<10?"0":"")+e}function t6(e){return(e<10?"00":e<100?"0":"")+e}var r6={YYYY:e=>e.getFullYear(),YY:e=>(e.getFullYear()+"").slice(2),MMMM:(e,t)=>t.MMMM[e.getMonth()],MMM:(e,t)=>t.MMM[e.getMonth()],MM:e=>fn(e.getMonth()+1),M:e=>e.getMonth()+1,DD:e=>fn(e.getDate()),D:e=>e.getDate(),WWWW:(e,t)=>t.WWWW[e.getDay()],WWW:(e,t)=>t.WWW[e.getDay()],HH:e=>fn(e.getHours()),H:e=>e.getHours(),h:e=>{let t=e.getHours();return t==0?12:t>12?t-12:t},AA:e=>e.getHours()>=12?"PM":"AM",aa:e=>e.getHours()>=12?"pm":"am",a:e=>e.getHours()>=12?"p":"a",mm:e=>fn(e.getMinutes()),m:e=>e.getMinutes(),ss:e=>fn(e.getSeconds()),s:e=>e.getSeconds(),fff:e=>t6(e.getMilliseconds())};function dc(e,t){t=t||e6;let i=[];let o=/\{([a-z]+)\}|[^{]+/gi,r;while(r=o.exec(e))i.push(r[0][0]=="{"?r6[r[1]]:r[0]);return a=>{let n="";for(let p=0;p<i.length;p++)n+=typeof i[p]=="string"?i[p]:i[p](a,t);return n}}var o6=new Intl.DateTimeFormat().resolvedOptions().timeZone;function i6(e,t){let i;if(t=="UTC"||t=="Etc/UTC")i=new Date(+e+e.getTimezoneOffset()*6e4);else if(t==o6)i=e;else{i=new Date(e.toLocaleString("en-US",{timeZone:t}));i.setMilliseconds(e.getMilliseconds())}return i}var G5=e=>e%1==0;var xs=[1,2,2.5,5];var a6=wn(10,-32,0,xs);var q5=wn(10,0,32,xs);var n6=q5.filter(G5);var Ti=a6.concat(q5);var pc="\n";var Y5="{YYYY}";var u5=pc+Y5;var Q5="{M}/{D}";var gn=pc+Q5;var ys=gn+"/{YY}";var K5="{aa}";var l6="{h}:{mm}";var ya=l6+K5;var f5=pc+ya;var v5=":{ss}";var Ie=null;function X5(e){let t=e*1e3,i=t*60,o=i*60,r=o*24,a=r*30,n=r*365;let p=e==1?wn(10,0,3,xs).filter(G5):wn(10,-3,0,xs);let d=p.concat([t,t*5,t*10,t*15,t*30,i,i*5,i*10,i*15,i*30,o,o*2,o*3,o*4,o*6,o*8,o*12,r,r*2,r*3,r*4,r*5,r*6,r*7,r*8,r*9,r*10,r*15,a,a*2,a*3,a*4,a*6,n,n*2,n*5,n*10,n*25,n*50,n*100]);const f=[[n,Y5,Ie,Ie,Ie,Ie,Ie,Ie,1],[r*28,"{MMM}",u5,Ie,Ie,Ie,Ie,Ie,1],[r,Q5,u5,Ie,Ie,Ie,Ie,Ie,1],[o,"{h}"+K5,ys,Ie,gn,Ie,Ie,Ie,1],[i,ya,ys,Ie,gn,Ie,Ie,Ie,1],[t,v5,ys+" "+ya,Ie,gn+" "+ya,Ie,f5,Ie,1],[e,v5+".{fff}",ys+" "+ya,Ie,gn+" "+ya,Ie,f5,Ie,1]];function g(m){return(u,M,C,A,H,_)=>{let S=[];let E=H>=n;let D=H>=a&&H<n;let K=m(C);let I=qe(K*e,3);let Y=F1(K.getFullYear(),E?0:K.getMonth(),D||E?1:K.getDate());let R=qe(Y*e,3);if(D||E){let B=D?H/a:0;let F=E?H/n:0;let z=I==R?I:qe(F1(Y.getFullYear()+F,Y.getMonth()+B,1)*e,3);let ee=new Date(ut(z/e));let T=ee.getFullYear();let Z=ee.getMonth();for(let q=0;z<=A;q++){let j=F1(T+F*q,Z+B*q,1);let P=j-m(qe(j*e,3));z=qe((+j+P)*e,3);if(z<=A)S.push(z)}}else{let B=H>=r?r:H;let F=hr(C)-hr(I);let z=R+F+Hs(I-R,B);S.push(z);let ee=m(z);let T=ee.getHours()+ee.getMinutes()/i+ee.getSeconds()/o;let Z=H/o;let q=u.axes[M]._space;let j=_/q;while(1){z=qe(z+H,e==1?0:3);if(z>A)break;if(Z>1){let P=hr(qe(T+Z,6))%24;let be=m(z);let he=be.getHours();let se=he-P;if(se>1)se=-1;z-=se*o;T=(T+Z)%24;let ke=S[S.length-1];let W=qe((z-ke)/H,3);if(W*j>=.7)S.push(z)}else S.push(z)}}return S}}return[d,f,g]}var[s6,c6,d6]=X5(1);var[p6,h6,u6]=X5(.001);wn(2,-53,53,[1]);function m5(e,t){return e.map(i=>i.map((o,r)=>r==0||r==8||o==null?o:t(r==1||i[8]==0?o:i[1]+o)))}function g5(e,t){return(i,o,r,a,n)=>{let p=t.find(C=>n>=C[0])||t[t.length-1];let d;let f;let g;let m;let u;let M;return o.map(C=>{let A=e(C);let H=A.getFullYear();let _=A.getMonth();let S=A.getDate();let E=A.getHours();let D=A.getMinutes();let K=A.getSeconds();let I=H!=d&&p[2]||_!=f&&p[3]||S!=g&&p[4]||E!=m&&p[5]||D!=u&&p[6]||K!=M&&p[7]||p[1];d=H;f=_;g=S;m=E;u=D;M=K;return I(A)})}}function f6(e,t){let i=dc(t);return(o,r,a,n,p)=>r.map(d=>i(e(d)))}function F1(e,t,i){return new Date(e,t,i)}function b5(e,t){return t(e)}var v6="{YYYY}-{MM}-{DD} {h}:{mm}{aa}";function y5(e,t){return(i,o,r,a)=>a==null?ic:t(e(o))}function m6(e,t){let i=e.series[t];return i.width?i.stroke(e,t):i.points.width?i.points.stroke(e,t):null}function g6(e,t){return e.series[t].fill(e,t)}var b6={show:true,live:true,isolate:false,mount:O3,markers:{show:true,width:2,stroke:m6,fill:g6,dash:"solid"},idx:null,idxs:null,values:[]};function y6(e,t){let i=e.cursor.points;let o=Vr();let r=i.size(e,t);Je(o,vn,r);Je(o,mn,r);let a=r/-2;Je(o,"marginLeft",a);Je(o,"marginTop",a);let n=i.width(e,t,r);n&&Je(o,"borderWidth",n);return o}function w6(e,t){let i=e.series[t].points;return i._fill||i._stroke}function C6(e,t){let i=e.series[t].points;return i._stroke||i._fill}function k6(e,t){let i=e.series[t].points;return i.size}var U1=[0,0];function L6(e,t,i){U1[0]=t;U1[1]=i;return U1}function ws(e,t,i,o=true){return r=>{r.button==0&&(!o||r.target==t)&&i(r)}}function W1(e,t,i,o=true){return r=>{(!o||r.target==t)&&i(r)}}var x6={show:true,x:true,y:true,lock:false,move:L6,points:{one:false,show:y6,size:k6,width:0,stroke:C6,fill:w6},bind:{mousedown:ws,mouseup:ws,click:ws,dblclick:ws,mousemove:W1,mouseleave:W1,mouseenter:W1},drag:{setScale:true,x:true,y:false,dist:0,uni:null,click:(e,t)=>{t.stopPropagation();t.stopImmediatePropagation()},_x:false,_y:false},focus:{dist:(e,t,i,o,r)=>o-r,prox:-1,bias:0},hover:{skip:[void 0],prox:null,bias:0},left:-10,top:-10,idx:null,dataIdx:null,idxs:null,event:null};var J5={show:true,stroke:"rgba(0,0,0,0.07)",width:2};var hc=lt({},J5,{filter:E5});var eh=lt({},hc,{size:10});var th=lt({},J5,{show:false});var uc='12px system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji"';var rh="bold "+uc;var oh=1.5;var w5={show:true,scale:"x",stroke:oc,space:50,gap:5,alignTo:1,size:50,labelGap:0,labelSize:30,labelFont:rh,side:2,grid:hc,ticks:eh,border:th,font:uc,lineGap:oh,rotate:0};var $6="Value";var M6="Time";var C5={show:true,scale:"x",auto:false,sorted:1,min:Ge,max:-Ge,idxs:[]};function H6(e,t,i,o,r){return t.map(a=>a==null?"":sc(a))}function S6(e,t,i,o,r,a,n){let p=[];let d=Jo.get(r)||0;i=n?i:qe(Hs(i,r),d);for(let f=i;f<=o;f=qe(f+r,d))p.push(Object.is(f,-0)?0:f);return p}function X1(e,t,i,o,r,a,n){const p=[];const d=e.scales[e.axes[t].scale].log;const f=d==10?_o:B5;const g=hr(f(i));r=Ca(d,g);if(d==10)r=Ti[Gr(r,Ti)];let m=i;let u=r*d;if(d==10)u=Ti[Gr(u,Ti)];do{p.push(m);m=m+r;if(d==10&&!Jo.has(m))m=qe(m,Jo.get(r));if(m>=u){r=m;u=r*d;if(d==10)u=Ti[Gr(u,Ti)]}}while(m<=o);return p}function _6(e,t,i,o,r,a,n){let p=e.scales[e.axes[t].scale];let d=p.asinh;let f=o>d?X1(e,t,Ut(d,i),o,r):[d];let g=o>=0&&i<=0?[0]:[];let m=i<-d?X1(e,t,Ut(d,-o),-i,r):[d];return m.reverse().map(u=>-u).concat(g,f)}var ih=/./;var V6=/[12357]/;var A6=/[125]/;var k5=/1/;var J1=(e,t,i,o)=>e.map((r,a)=>t==4&&r==0||a%o==0&&i.test(r.toExponential()[r<0?1:0])?r:null);function Z6(e,t,i,o,r){let a=e.axes[i];let n=a.scale;let p=e.scales[n];let d=e.valToPos;let f=a._space;let g=d(10,n);let m=d(9,n)-g>=f?ih:d(7,n)-g>=f?V6:d(5,n)-g>=f?A6:k5;if(m==k5){let u=ft(d(1,n)-g);if(u<f)return J1(t.slice().reverse(),p.distr,m,Ar(f/u)).reverse()}return J1(t,p.distr,m,1)}function T6(e,t,i,o,r){let a=e.axes[i];let n=a.scale;let p=a._space;let d=e.valToPos;let f=ft(d(1,n)-d(2,n));if(f<p)return J1(t.slice().reverse(),3,ih,Ar(p/f)).reverse();return t}function P6(e,t,i,o){return o==null?ic:t==null?"":sc(t)}var L5={show:true,scale:"y",stroke:oc,space:30,gap:5,alignTo:1,size:50,labelGap:0,labelSize:30,labelFont:rh,side:3,grid:hc,ticks:eh,border:th,font:uc,lineGap:oh,rotate:0};function z6(e,t){let i=3+(e||1)*2;return qe(i*t,3)}function B6(e,t){let{scale:i,idxs:o}=e.series[0];let r=e._data[0];let a=e.valToPos(r[o[0]],i,true);let n=e.valToPos(r[o[1]],i,true);let p=ft(n-a);let d=e.series[t];let f=p/(d.points.space*De);return o[1]-o[0]<=f}var x5={scale:null,auto:true,sorted:0,min:Ge,max:-Ge};var ah=(e,t,i,o,r)=>r;var $5={show:true,auto:true,sorted:0,gaps:ah,alpha:1,facets:[lt({},x5,{scale:"x"}),lt({},x5,{scale:"y"})]};var M5={scale:"y",auto:true,sorted:0,show:true,spanGaps:false,gaps:ah,alpha:1,points:{show:B6,filter:null},values:null,min:Ge,max:-Ge,idxs:[],path:null,clip:null};function O6(e,t,i,o,r){return i/10}var nh={time:s3,auto:true,distr:1,log:10,asinh:1,min:null,max:null,dir:1,ori:0};var D6=lt({},nh,{time:false,ori:1});var H5={};function lh(e,t){let i=H5[e];if(!i){i={key:e,plots:[],sub(o){i.plots.push(o)},unsub(o){i.plots=i.plots.filter(r=>r!=o)},pub(o,r,a,n,p,d,f){for(let g=0;g<i.plots.length;g++)i.plots[g]!=r&&i.plots[g].pub(o,r,a,n,p,d,f)}};if(e!=null)H5[e]=i}return i}var xa=1<<0;var ec=1<<1;function Oi(e,t,i){const o=e.mode;const r=e.series[t];const a=o==2?e._data[t]:e._data;const n=e.scales;const p=e.bbox;let d=a[0],f=o==2?a[1]:a[t],g=o==2?n[r.facets[0].scale]:n[e.series[0].scale],m=o==2?n[r.facets[1].scale]:n[r.scale],u=p.left,M=p.top,C=p.width,A=p.height,H=e.valToPosH,_=e.valToPosV;return g.ori==0?i(r,d,f,g,m,H,_,u,M,C,A,Vs,Ma,Zs,ch,ph):i(r,d,f,g,m,_,H,M,u,A,C,As,Ha,mc,dh,hh)}function fc(e,t){let i=0;let o=0;let r=Pe(e.bands,cc);for(let a=0;a<r.length;a++){let n=r[a];if(n.series[0]==t)i=n.dir;else if(n.series[1]==t){if(n.dir==1)o|=1;else o|=2}}return[i,o==1?-1:o==2?1:o==3?2:0]}function E6(e,t,i,o,r){let a=e.mode;let n=e.series[t];let p=a==2?n.facets[1].scale:n.scale;let d=e.scales[p];return r==-1?d.min:r==1?d.max:d.distr==3?d.dir==1?d.min:d.max:0}function Vo(e,t,i,o,r,a){return Oi(e,t,(n,p,d,f,g,m,u,M,C,A,H)=>{let _=n.pxRound;const S=f.dir*(f.ori==0?1:-1);const E=f.ori==0?Ma:Ha;let D,K;if(S==1){D=i;K=o}else{D=o;K=i}let I=_(m(p[D],f,A,M));let Y=_(u(d[D],g,H,C));let R=_(m(p[K],f,A,M));let B=_(u(a==1?g.max:g.min,g,H,C));let F=new Path2D(r);E(F,R,B);E(F,I,B);E(F,I,Y);return F})}function _s(e,t,i,o,r,a){let n=null;if(e.length>0){n=new Path2D;const p=t==0?Zs:mc;let d=i;for(let m=0;m<e.length;m++){let u=e[m];if(u[1]>u[0]){let M=u[0]-d;M>0&&p(n,d,o,M,o+a);d=u[1]}}let f=i+r-d;let g=10;f>0&&p(n,d,o-g/2,f,o+a+g)}return n}function R6(e,t,i){let o=e[e.length-1];if(o&&o[0]==t)o[1]=i;else e.push([t,i])}function vc(e,t,i,o,r,a,n){let p=[];let d=e.length;for(let f=r==1?i:o;f>=i&&f<=o;f+=r){let g=t[f];if(g===null){let m=f,u=f;if(r==1){while(++f<=o&&t[f]===null)u=f}else{while(--f>=i&&t[f]===null)u=f}let M=a(e[m]);let C=u==m?M:a(e[u]);let A=m-r;let H=n<=0&&A>=0&&A<d?a(e[A]):M;M=H;let _=u+r;let S=n>=0&&_>=0&&_<d?a(e[_]):C;C=S;if(C>=M)p.push([M,C])}}return p}function S5(e){return e==0?D5:e==1?ut:t=>Zi(t,e)}function sh(e){let t=e==0?Vs:As;let i=e==0?(r,a,n,p,d,f)=>{r.arcTo(a,n,p,d,f)}:(r,a,n,p,d,f)=>{r.arcTo(n,a,d,p,f)};let o=e==0?(r,a,n,p,d)=>{r.rect(a,n,p,d)}:(r,a,n,p,d)=>{r.rect(n,a,d,p)};return(r,a,n,p,d,f=0,g=0)=>{if(f==0&&g==0)o(r,a,n,p,d);else{f=qr(f,p/2,d/2);g=qr(g,p/2,d/2);t(r,a+f,n);i(r,a+p,n,a+p,n+d,f);i(r,a+p,n+d,a,n+d,g);i(r,a,n+d,a,n,g);i(r,a,n,a+p,n,f);r.closePath()}}}var Vs=(e,t,i)=>{e.moveTo(t,i)};var As=(e,t,i)=>{e.moveTo(i,t)};var Ma=(e,t,i)=>{e.lineTo(t,i)};var Ha=(e,t,i)=>{e.lineTo(i,t)};var Zs=sh(0);var mc=sh(1);var ch=(e,t,i,o,r,a)=>{e.arc(t,i,o,r,a)};var dh=(e,t,i,o,r,a)=>{e.arc(i,t,o,r,a)};var ph=(e,t,i,o,r,a,n)=>{e.bezierCurveTo(t,i,o,r,a,n)};var hh=(e,t,i,o,r,a,n)=>{e.bezierCurveTo(i,t,r,o,n,a)};function uh(e){return(t,i,o,r,a)=>{return Oi(t,i,(n,p,d,f,g,m,u,M,C,A,H)=>{let{pxRound:_,points:S}=n;let E,D;if(f.ori==0){E=Vs;D=ch}else{E=As;D=dh}const K=qe(S.width*De,3);let I=(S.size-S.width)/2*De;let Y=qe(I*2,3);let R=new Path2D;let B=new Path2D;let{left:F,top:z,width:ee,height:T}=t.bbox;Zs(B,F-Y,z-Y,ee+Y*2,T+Y*2);const Z=q=>{if(d[q]!=null){let j=_(m(p[q],f,A,M));let P=_(u(d[q],g,H,C));E(R,j+I,P);D(R,j,P,I,0,Cs*2)}};if(a)a.forEach(Z);else{for(let q=o;q<=r;q++)Z(q)}return{stroke:K>0?R:null,fill:R,clip:B,flags:xa|ec}})}}function fh(e){return(t,i,o,r,a,n)=>{if(o!=r){if(a!=o&&n!=o)e(t,i,o);if(a!=r&&n!=r)e(t,i,r);e(t,i,n)}}}var I6=fh(Ma);var N6=fh(Ha);function vh(e){const t=Pe(e?.alignGaps,0);return(i,o,r,a)=>{return Oi(i,o,(n,p,d,f,g,m,u,M,C,A,H)=>{[r,a]=$s(d,r,a);let _=n.pxRound;let S=T=>_(m(T,f,A,M));let E=T=>_(u(T,g,H,C));let D,K;if(f.ori==0){D=Ma;K=I6}else{D=Ha;K=N6}const I=f.dir*(f.ori==0?1:-1);const Y={stroke:new Path2D,fill:null,clip:null,band:null,gaps:null,flags:xa};const R=Y.stroke;let B=false;const F=a-r>=A*4;if(F){let T=N=>i.posToVal(N,f.key,true);let Z=null,q=null,j,P,be;let he=S(p[I==1?r:a]);let se=S(p[r]);let ke=S(p[a]);let W=T(I==1?se+1:ke-1);for(let N=I==1?r:a;N>=r&&N<=a;N+=I){let ye=p[N];let we=I==1?ye<W:ye>W;let oe=we?he:S(ye);let ie=d[N];if(oe==he){if(ie!=null){P=ie;if(Z==null){D(R,oe,E(P));j=Z=q=P}else{if(P<Z)Z=P;else if(P>q)q=P}}else{if(ie===null)B=true}}else{if(Z!=null)K(R,he,E(Z),E(q),E(j),E(P));if(ie!=null){P=ie;D(R,oe,E(P));Z=q=j=P}else{Z=q=null;if(ie===null)B=true}he=oe;W=T(he+I)}}if(Z!=null&&Z!=q&&be!=he)K(R,he,E(Z),E(q),E(j),E(P))}else{for(let T=I==1?r:a;T>=r&&T<=a;T+=I){let Z=d[T];if(Z===null)B=true;else if(Z!=null)D(R,S(p[T]),E(Z))}}let[z,ee]=fc(i,o);if(n.fill!=null||z!=0){let T=Y.fill=new Path2D(R);let Z=n.fillTo(i,o,n.min,n.max,z);let q=E(Z);let j=S(p[r]);let P=S(p[a]);if(I==-1)[P,j]=[j,P];D(T,P,q);D(T,j,q)}if(!n.spanGaps){let T=[];B&&T.push(...vc(p,d,r,a,I,S,t));Y.gaps=T=n.gaps(i,o,r,a,T);Y.clip=_s(T,f.ori,M,C,A,H)}if(ee!=0){Y.band=ee==2?[Vo(i,o,r,a,R,-1),Vo(i,o,r,a,R,1)]:Vo(i,o,r,a,R,ee)}return Y})}}function j6(e){const t=Pe(e.align,1);const i=Pe(e.ascDesc,false);const o=Pe(e.alignGaps,0);const r=Pe(e.extend,false);return(a,n,p,d)=>{return Oi(a,n,(f,g,m,u,M,C,A,H,_,S,E)=>{[p,d]=$s(m,p,d);let D=f.pxRound;let{left:K,width:I}=a.bbox;let Y=se=>D(C(se,u,S,H));let R=se=>D(A(se,M,E,_));let B=u.ori==0?Ma:Ha;const F={stroke:new Path2D,fill:null,clip:null,band:null,gaps:null,flags:xa};const z=F.stroke;const ee=u.dir*(u.ori==0?1:-1);let T=R(m[ee==1?p:d]);let Z=Y(g[ee==1?p:d]);let q=Z;let j=Z;if(r&&t==-1){j=K;B(z,j,T)}B(z,Z,T);for(let se=ee==1?p:d;se>=p&&se<=d;se+=ee){let ke=m[se];if(ke==null)continue;let W=Y(g[se]);let N=R(ke);if(t==1)B(z,W,T);else B(z,q,N);B(z,W,N);T=N;q=W}let P=q;if(r&&t==1){P=K+I;B(z,P,T)}let[be,he]=fc(a,n);if(f.fill!=null||be!=0){let se=F.fill=new Path2D(z);let ke=f.fillTo(a,n,f.min,f.max,be);let W=R(ke);B(se,P,W);B(se,j,W)}if(!f.spanGaps){let se=[];se.push(...vc(g,m,p,d,ee,Y,o));let ke=f.width*De/2;let W=i||t==1?ke:-ke;let N=i||t==-1?-ke:ke;se.forEach(ye=>{ye[0]+=W;ye[1]+=N});F.gaps=se=f.gaps(a,n,p,d,se);F.clip=_s(se,u.ori,H,_,S,E)}if(he!=0){F.band=he==2?[Vo(a,n,p,d,z,-1),Vo(a,n,p,d,z,1)]:Vo(a,n,p,d,z,he)}return F})}}function _5(e,t,i,o,r,a,n=Ge){if(e.length>1){let p=null;for(let d=0,f=Infinity;d<e.length;d++){if(t[d]!==void 0){if(p!=null){let g=ft(e[d]-e[p]);if(g<f){f=g;n=ft(i(e[d],o,r,a)-i(e[p],o,r,a))}}p=d}}}return n}function F6(e){e=e||yn;const t=Pe(e.size,[.6,Ge,1]);const i=e.align||0;const o=e.gap||0;let r=e.radius;r=r==null?[0,0]:typeof r=="number"?[r,0]:r;const a=_e(r);const n=1-t[0];const p=Pe(t[1],Ge);const d=Pe(t[2],1);const f=Pe(e.disp,yn);const g=Pe(e.each,M=>{});const{fill:m,stroke:u}=f;return(M,C,A,H)=>{return Oi(M,C,(_,S,E,D,K,I,Y,R,B,F,z)=>{let ee=_.pxRound;let T=i;let Z=o*De;let q=p*De;let j=d*De;let P,be;if(D.ori==0)[P,be]=a(M,C);else[be,P]=a(M,C);const he=D.dir*(D.ori==0?1:-1);let se=D.ori==0?Zs:mc;let ke=D.ori==0?g:(re,Ue,st,Ii,oi,Yr,ii)=>{g(re,Ue,st,oi,Ii,ii,Yr)};let W=Pe(M.bands,cc).find(re=>re.series[0]==C);let N=W!=null?W.dir:0;let ye=_.fillTo(M,C,_.min,_.max,N);let we=ee(Y(ye,K,z,B));let oe,ie,ue,Ee=F;let ne=ee(_.width*De);let er=false;let fr=null;let vr=null;let Ao=null;let Di=null;if(m!=null&&(ne==0||u!=null)){er=true;fr=m.values(M,C,A,H);vr=new Map;new Set(fr).forEach(re=>{if(re!=null)vr.set(re,new Path2D)});if(ne>0){Ao=u.values(M,C,A,H);Di=new Map;new Set(Ao).forEach(re=>{if(re!=null)Di.set(re,new Path2D)})}}let{x0:Ei,size:_a}=f;if(Ei!=null&&_a!=null){T=1;S=Ei.values(M,C,A,H);if(Ei.unit==2)S=S.map(st=>M.posToVal(R+st*F,D.key,true));let re=_a.values(M,C,A,H);if(_a.unit==2)ie=re[0]*F;else ie=I(re[0],D,F,R)-I(0,D,F,R);Ee=_5(S,E,I,D,F,R,Ee);let Ue=Ee-ie;ue=Ue+Z}else{Ee=_5(S,E,I,D,F,R,Ee);let re=Ee*n;ue=re+Z;ie=Ee-ue}if(ue<1)ue=0;if(ne>=ie/2)ne=0;if(ue<5)ee=D5;let Cn=ue>0;let ti=Ee-ue-(Cn?ne:0);ie=ee(K1(ti,j,q));oe=(T==0?ie/2:T==he?0:ie)-T*he*((T==0?Z/2:0)+(Cn?ne/2:0));const Dt={stroke:null,fill:null,clip:null,band:null,gaps:null,flags:0};const Ri=er?null:new Path2D;let mo=null;if(W!=null)mo=M.data[W.series[1]];else{let{y0:re,y1:Ue}=f;if(re!=null&&Ue!=null){E=Ue.values(M,C,A,H);mo=re.values(M,C,A,H)}}let ri=P*ie;let Ce=be*ie;for(let re=he==1?A:H;re>=A&&re<=H;re+=he){let Ue=E[re];if(Ue==null)continue;if(mo!=null){let Wt=mo[re]??0;if(Ue-Wt==0)continue;we=Y(Wt,K,z,B)}let st=D.distr!=2||f!=null?S[re]:re;let Ii=I(st,D,F,R);let oi=Y(Pe(Ue,ye),K,z,B);let Yr=ee(Ii-oe);let ii=ee(Ut(oi,we));let tr=ee(qr(oi,we));let mr=ii-tr;if(Ue!=null){let Wt=Ue<0?Ce:ri;let Zr=Ue<0?ri:Ce;if(er){if(ne>0&&Ao[re]!=null)se(Di.get(Ao[re]),Yr,tr+hr(ne/2),ie,Ut(0,mr-ne),Wt,Zr);if(fr[re]!=null)se(vr.get(fr[re]),Yr,tr+hr(ne/2),ie,Ut(0,mr-ne),Wt,Zr)}else se(Ri,Yr,tr+hr(ne/2),ie,Ut(0,mr-ne),Wt,Zr);ke(M,C,re,Yr-ne/2,tr,ie+ne,mr)}}if(ne>0)Dt.stroke=er?Di:Ri;else if(!er){Dt._fill=_.width==0?_._fill:_._stroke??_._fill;Dt.width=0}Dt.fill=er?vr:Ri;return Dt})}}function U6(e,t){const i=Pe(t?.alignGaps,0);return(o,r,a,n)=>{return Oi(o,r,(p,d,f,g,m,u,M,C,A,H,_)=>{[a,n]=$s(f,a,n);let S=p.pxRound;let E=P=>S(u(P,g,H,C));let D=P=>S(M(P,m,_,A));let K,I,Y;if(g.ori==0){K=Vs;Y=Ma;I=ph}else{K=As;Y=Ha;I=hh}const R=g.dir*(g.ori==0?1:-1);let B=E(d[R==1?a:n]);let F=B;let z=[];let ee=[];for(let P=R==1?a:n;P>=a&&P<=n;P+=R){let be=f[P];if(be!=null){let he=d[P];let se=E(he);z.push(F=se);ee.push(D(f[P]))}}const T={stroke:e(z,ee,K,Y,I,S),fill:null,clip:null,band:null,gaps:null,flags:xa};const Z=T.stroke;let[q,j]=fc(o,r);if(p.fill!=null||q!=0){let P=T.fill=new Path2D(Z);let be=p.fillTo(o,r,p.min,p.max,q);let he=D(be);Y(P,F,he);Y(P,B,he)}if(!p.spanGaps){let P=[];P.push(...vc(d,f,a,n,R,E,i));T.gaps=P=p.gaps(o,r,a,n,P);T.clip=_s(P,g.ori,C,A,H,_)}if(j!=0){T.band=j==2?[Vo(o,r,a,n,Z,-1),Vo(o,r,a,n,Z,1)]:Vo(o,r,a,n,Z,j)}return T})}}function W6(e){return U6(G6,e)}function G6(e,t,i,o,r,a){const n=e.length;if(n<2)return null;const p=new Path2D;i(p,e[0],t[0]);if(n==2)o(p,e[1],t[1]);else{let d=Array(n),f=Array(n-1),g=Array(n-1),m=Array(n-1);for(let u=0;u<n-1;u++){g[u]=t[u+1]-t[u];m[u]=e[u+1]-e[u];f[u]=g[u]/m[u]}d[0]=f[0];for(let u=1;u<n-1;u++){if(f[u]===0||f[u-1]===0||f[u-1]>0!==f[u]>0)d[u]=0;else{d[u]=3*(m[u-1]+m[u])/((2*m[u]+m[u-1])/f[u-1]+(m[u]+2*m[u-1])/f[u]);if(!isFinite(d[u]))d[u]=0}}d[n-1]=f[n-2];for(let u=0;u<n-1;u++){r(p,e[u]+m[u]/3,t[u]+d[u]*m[u]/3,e[u+1]-m[u]/3,t[u+1]-d[u+1]*m[u]/3,e[u+1],t[u+1])}}return p}var tc=new Set;function V5(){for(let e of tc)e.syncRect(true)}if($a){zi(H3,wa,V5);zi(S3,wa,V5,true);zi(ks,wa,()=>{Vt.pxRatio=De})}var q6=vh();var Y6=uh();function A5(e,t,i,o){let r=o?[e[0],e[1]].concat(e.slice(2)):[e[0]].concat(e.slice(1));return r.map((a,n)=>rc(a,n,t,i))}function Q6(e,t){return e.map((i,o)=>o==0?{}:lt({},t,i))}function rc(e,t,i,o){return lt({},t==0?i:o,e)}function mh(e,t,i){return t==null?ka:[t,i]}var K6=mh;function X6(e,t,i){return t==null?ka:Ls(t,i,lc,true)}function gh(e,t,i,o){return t==null?ka:Ms(t,i,e.scales[o].log,false)}var J6=gh;function bh(e,t,i,o){return t==null?ka:nc(t,i,e.scales[o].log,false)}var ef=bh;function tf(e,t,i,o,r){let a=Ut(c5(e),c5(t));let n=t-e;let p=Gr(r/o*n,i);do{let d=i[p];let f=o*d/n;if(f>=r&&a+(d<5?Jo.get(d):0)<=17)return[d,f]}while(++p<i.length);return[0,0]}function Z5(e){let t,i;e=e.replace(/(\d+)px/,(o,r)=>(t=ut((i=+r)*De))+"px");return[e,t,i]}function rf(e){if(e.show){[e.font,e.labelFont].forEach(t=>{let i=qe(t[2]*De,1);t[0]=t[0].replace(/[0-9.]+px/,i+"px");t[1]=i})}}function Vt(e,t,i){const o={mode:Pe(e.mode,1)};const r=o.mode;function a(s,v,b,y){let $=v.valToPct(s);return y+b*(v.dir==-1?1-$:$)}function n(s,v,b,y){let $=v.valToPct(s);return y+b*(v.dir==-1?$:1-$)}function p(s,v,b,y){return v.ori==0?a(s,v,b,y):n(s,v,b,y)}o.valToPosH=a;o.valToPosV=n;let d=false;o.status=0;const f=o.root=Vr(c3);if(e.id!=null)f.id=e.id;pr(f,e.class);if(e.title){let s=Vr(h3,f);s.textContent=e.title}const g=Wr("canvas");const m=o.ctx=g.getContext("2d");const u=Vr(u3,f);zi("click",u,s=>{if(s.target===C){let v=Qe!=Xi||et!=Ji;v&&Ht.click(o,s)}},true);const M=o.under=Vr(f3,u);u.appendChild(g);const C=o.over=Vr(v3,u);e=La(e);const A=+Pe(e.pxAlign,1);const H=S5(A);(e.plugins||[]).forEach(s=>{if(s.opts)e=s.opts(o,e)||e});const _=e.ms||.001;const S=o.series=r==1?A5(e.series||[],C5,M5,false):Q6(e.series||[null],$5);const E=o.axes=A5(e.axes||[],w5,L5,true);const D=o.scales={};const K=o.bands=e.bands||[];K.forEach(s=>{s.fill=_e(s.fill||null);s.dir=Pe(s.dir,-1)});const I=r==2?S[1].facets[0].scale:S[0].scale;const Y={axes:Ph,series:_h};const R=(e.drawOrder||["axes","series"]).map(s=>Y[s]);function B(s){const v=s.distr==3?b=>_o(b>0?b:s.clamp(o,b,s.min,s.max,s.key)):s.distr==4?b=>j1(b,s.asinh):s.distr==100?b=>s.fwd(b):b=>b;return b=>{let y=v(b);let{_min:$,_max:V}=s;let O=V-$;return(y-$)/O}}function F(s){let v=D[s];if(v==null){let b=(e.scales||yn)[s]||yn;if(b.from!=null){F(b.from);let y=lt({},D[b.from],b,{key:s});y.valToPct=B(y);D[s]=y}else{v=D[s]=lt({},s==I?nh:D6,b);v.key=s;let y=v.time;let $=v.range;let V=Xo($);if(s!=I||r==2&&!y){if(V&&($[0]==null||$[1]==null)){$={min:$[0]==null?n5:{mode:1,hard:$[0],soft:$[0]},max:$[1]==null?n5:{mode:1,hard:$[1],soft:$[1]}};V=false}if(!V&&Ss($)){let O=$;$=(U,G,X)=>G==null?ka:Ls(G,X,O)}}v.range=_e($||(y?K6:s==I?v.distr==3?J6:v.distr==4?ef:mh:v.distr==3?gh:v.distr==4?bh:X6));v.auto=_e(V?false:v.auto);v.clamp=_e(v.clamp||O6);v._min=v._max=null;v.valToPct=B(v)}}}F("x");F("y");if(r==1){S.forEach(s=>{F(s.scale)})}E.forEach(s=>{F(s.scale)});for(let s in e.scales)F(s);const z=D[I];const ee=z.distr;let T,Z;if(z.ori==0){pr(f,d3);T=a;Z=n}else{pr(f,p3);T=n;Z=a}const q={};for(let s in D){let v=D[s];if(v.min!=null||v.max!=null){q[s]={min:v.min,max:v.max};v.min=v.max=null}}const j=e.tzDate||(s=>new Date(ut(s/_)));const P=e.fmtDate||dc;const be=_==1?d6(j):u6(j);const he=g5(j,m5(_==1?c6:h6,P));const se=y5(j,b5(v6,P));const ke=[];const W=o.legend=lt({},b6,e.legend);const N=o.cursor=lt({},x6,{drag:{y:r==2}},e.cursor);const ye=W.show;const we=N.show;const oe=W.markers;{W.idxs=ke;oe.width=_e(oe.width);oe.dash=_e(oe.dash);oe.stroke=_e(oe.stroke);oe.fill=_e(oe.fill)}let ie;let ue;let Ee;let ne=[];let er=[];let fr;let vr=false;let Ao={};if(W.live){const s=S[1]?S[1].values:null;vr=s!=null;fr=vr?s(o,1,0):{_:0};for(let v in fr)Ao[v]=ic}if(ye){ie=Wr("table",C3,f);Ee=Wr("tbody",null,ie);W.mount(o,ie);if(vr){ue=Wr("thead",null,ie,Ee);let s=Wr("tr",null,ue);Wr("th",null,s);for(var Di in fr)Wr("th",G0,s).textContent=Di}else{pr(ie,L3);W.live&&pr(ie,k3)}}const Ei={show:true};const _a={show:false};function Cn(s,v){if(v==0&&(vr||!W.live||r==2))return ka;let b=[];let y=Wr("tr",x3,Ee,Ee.childNodes[v]);pr(y,s.class);if(!s.show)pr(y,Pi);let $=Wr("th",null,y);if(oe.show){let U=Vr($3,$);if(v>0){let G=oe.width(o,v);if(G)U.style.border=G+"px "+oe.dash(o,v)+" "+oe.stroke(o,v);U.style.background=oe.fill(o,v)}}let V=Vr(G0,$);if(s.label instanceof HTMLElement)V.appendChild(s.label);else V.textContent=s.label;if(v>0){if(!oe.show)V.style.color=s.width>0?oe.stroke(o,v):oe.fill(o,v);Dt("click",$,U=>{if(N._lock)return;ni(U);let G=S.indexOf(s);if((U.ctrlKey||U.metaKey)!=W.isolate){let X=S.some((te,ae)=>ae>0&&ae!=G&&te.show);S.forEach((te,ae)=>{ae>0&&Kr(ae,X?ae==G?Ei:_a:Ei,true,it.setSeries)})}else Kr(G,{show:!s.show},true,it.setSeries)},false);if(ji){Dt(K0,$,U=>{if(N._lock)return;ni(U);Kr(S.indexOf(s),ta,true,it.setSeries)},false)}}for(var O in fr){let U=Wr("td",M3,y);U.textContent="--";b.push(U)}return[y,b]}const ti=new Map;function Dt(s,v,b,y=true){const $=ti.get(v)||{};const V=N.bind[s](o,v,b,y);if(V){zi(s,v,$[s]=V);ti.set(v,$)}}function Ri(s,v,b){const y=ti.get(v)||{};for(let $ in y){if(s==null||$==s){Q1($,v,y[$]);delete y[$]}}if(s==null)ti.delete(v)}let mo=0;let ri=0;let Ce=0;let re=0;let Ue=0;let st=0;let Ii=Ue;let oi=st;let Yr=Ce;let ii=re;let tr=0;let mr=0;let Wt=0;let Zr=0;o.bbox={};let Ts=false;let kn=false;let Ni=false;let ai=false;let Ln=false;let gr=false;function Ps(s,v,b){if(b||(s!=o.width||v!=o.height))gc(s,v);qi(false);Ni=true;kn=true;Yi()}function gc(s,v){o.width=mo=Ce=s;o.height=ri=re=v;Ue=st=0;kh();Lh();let b=o.bbox;tr=b.left=Zi(Ue*De,.5);mr=b.top=Zi(st*De,.5);Wt=b.width=Zi(Ce*De,.5);Zr=b.height=Zi(re*De,.5)}const yh=3;function wh(){let s=false;let v=0;while(!s){v++;let b=Zh(v);let y=Th(v);s=v==yh||b&&y;if(!s){gc(o.width,o.height);kn=true}}}function Ch({width:s,height:v}){Ps(s,v)}o.setSize=Ch;function kh(){let s=false;let v=false;let b=false;let y=false;E.forEach(($,V)=>{if($.show&&$._show){let{side:O,_size:U}=$;let G=O%2;let X=$.label!=null?$.labelSize:0;let te=U+X;if(te>0){if(G){Ce-=te;if(O==3){Ue+=te;y=true}else b=true}else{re-=te;if(O==0){st+=te;s=true}else v=true}}}});li[0]=s;li[1]=b;li[2]=v;li[3]=y;Ce-=Zo[1]+Zo[3];Ue+=Zo[3];re-=Zo[2]+Zo[0];st+=Zo[0]}function Lh(){let s=Ue+Ce;let v=st+re;let b=Ue;let y=st;function $(V,O){switch(V){case 1:s+=O;return s-O;case 2:v+=O;return v-O;case 3:b-=O;return b+O;case 0:y-=O;return y+O}}E.forEach((V,O)=>{if(V.show&&V._show){let U=V.side;V._pos=$(U,V._size);if(V.label!=null)V._lpos=$(U,V.labelSize)}})}if(N.dataIdx==null){let s=N.hover;let v=s.skip=new Set(s.skip??[]);v.add(void 0);let b=s.prox=_e(s.prox);let y=s.bias??=0;N.dataIdx=($,V,O,U)=>{if(V==0)return O;let G=O;let X=b($,V,O,U)??Ge;let te=X>=0&&X<Ge;let ae=z.ori==0?Ce:re;let ge=N.left;let ze=t[0];let Ze=t[V];if(v.has(Ze[O])){G=null;let xe=null,fe=null,le;if(y==0||y==-1){le=O;while(xe==null&&le-- >0){if(!v.has(Ze[le]))xe=le}}if(y==0||y==1){le=O;while(fe==null&&le++<Ze.length){if(!v.has(Ze[le]))fe=le}}if(xe!=null||fe!=null){if(te){let Xe=xe==null?-Infinity:T(ze[xe],z,ae,0);let tt=fe==null?Infinity:T(ze[fe],z,ae,0);let Ct=ge-Xe;let je=tt-ge;if(Ct<=je){if(Ct<=X)G=xe}else{if(je<=X)G=fe}}else{G=fe==null?xe:xe==null?fe:O-xe<=fe-O?xe:fe}}}else if(te){let xe=ft(ge-T(ze[O],z,ae,0));if(xe>X)G=null}return G}}const ni=s=>{N.event=s};N.idxs=ke;N._lock=false;let At=N.points;At.show=_e(At.show);At.size=_e(At.size);At.stroke=_e(At.stroke);At.width=_e(At.width);At.fill=_e(At.fill);const Qr=o.focus=lt({},e.focus||{alpha:.3},N.focus);const ji=Qr.prox>=0;const Fi=ji&&At.one;let br=[];let Ui=[];let Wi=[];function bc(s,v){let b=At.show(o,v);if(b instanceof HTMLElement){pr(b,w3);pr(b,s.class);vo(b,-10,-10,Ce,re);C.insertBefore(b,br[v]);return b}}function yc(s,v){if(r==1||v>0){let b=r==1&&D[s.scale].time;let y=s.value;s.value=b?h5(y)?y5(j,b5(y,P)):y||se:y||P6;s.label=s.label||(b?M6:$6)}if(Fi||v>0){s.width=s.width==null?1:s.width;s.paths=s.paths||q6||D3;s.fillTo=_e(s.fillTo||E6);s.pxAlign=+Pe(s.pxAlign,A);s.pxRound=S5(s.pxAlign);s.stroke=_e(s.stroke||null);s.fill=_e(s.fill||null);s._stroke=s._fill=s._paths=s._focus=null;let b=z6(Ut(1,s.width),1);let y=s.points=lt({},{size:b,width:Ut(1,b*.2),stroke:s.stroke,space:b*2,paths:Y6,_stroke:null,_fill:null},s.points);y.show=_e(y.show);y.filter=_e(y.filter);y.fill=_e(y.fill);y.stroke=_e(y.stroke);y.paths=_e(y.paths);y.pxAlign=s.pxAlign}if(ye){let b=Cn(s,v);ne.splice(v,0,b[0]);er.splice(v,0,b[1]);W.values.push(null)}if(we){ke.splice(v,0,null);let b=null;if(Fi){if(v==0)b=bc(s,v)}else if(v>0)b=bc(s,v);br.splice(v,0,b);Ui.splice(v,0,0);Wi.splice(v,0,0)}wt("addSeries",v)}function xh(s,v){v=v==null?S.length:v;s=r==1?rc(s,v,C5,M5):rc(s,v,{},$5);S.splice(v,0,s);yc(S[v],v)}o.addSeries=xh;function $h(s){S.splice(s,1);if(ye){W.values.splice(s,1);er.splice(s,1);let v=ne.splice(s,1)[0];Ri(null,v.firstChild);v.remove()}if(we){ke.splice(s,1);br.splice(s,1)[0].remove();Ui.splice(s,1);Wi.splice(s,1)}wt("delSeries",s)}o.delSeries=$h;const li=[false,false,false,false];function Mh(s,v){s._show=s.show;if(s.show){let b=s.side%2;let y=D[s.scale];if(y==null){s.scale=b?S[1].scale:I;y=D[s.scale]}let $=y.time;s.size=_e(s.size);s.space=_e(s.space);s.rotate=_e(s.rotate);if(Xo(s.incrs)){s.incrs.forEach(O=>{!Jo.has(O)&&Jo.set(O,I5(O))})}s.incrs=_e(s.incrs||(y.distr==2?n6:$?_==1?s6:p6:Ti));s.splits=_e(s.splits||($&&y.distr==1?be:y.distr==3?X1:y.distr==4?_6:S6));s.stroke=_e(s.stroke);s.grid.stroke=_e(s.grid.stroke);s.ticks.stroke=_e(s.ticks.stroke);s.border.stroke=_e(s.border.stroke);let V=s.values;s.values=Xo(V)&&!Xo(V[0])?_e(V):$?Xo(V)?g5(j,m5(V,P)):h5(V)?f6(j,V):V||he:V||H6;s.filter=_e(s.filter||(y.distr>=3&&y.log==10?Z6:y.distr==3&&y.log==2?T6:E5));s.font=Z5(s.font);s.labelFont=Z5(s.labelFont);s._size=s.size(o,null,v,0);s._space=s._rotate=s._incrs=s._found=s._splits=s._values=null;if(s._size>0){li[v]=true;s._el=Vr(m3,u)}}}function Va(s,v,b,y){let[$,V,O,U]=b;let G=v%2;let X=0;if(G==0&&(U||V))X=v==0&&!$||v==2&&!O?ut(w5.size/3):0;if(G==1&&($||O))X=v==1&&!V||v==3&&!U?ut(L5.size/2):0;return X}const wc=o.padding=(e.padding||[Va,Va,Va,Va]).map(s=>_e(Pe(s,Va)));const Zo=o._padding=wc.map((s,v)=>s(o,v,li,0));let Mt;let mt=null;let gt=null;const xn=r==1?S[0].idxs:null;let Tr=null;let Aa=false;function Cc(s,v){t=s==null?[]:s;o.data=o._data=t;if(r==2){Mt=0;for(let b=1;b<S.length;b++)Mt+=t[b][0].length}else{if(t.length==0)o.data=o._data=t=[[]];Tr=t[0];Mt=Tr.length;let b=t;if(ee==2){b=t.slice();let y=b[0]=Array(Mt);for(let $=0;$<Mt;$++)y[$]=$}o._data=t=b}qi(true);wt("setData");if(ee==2){Ni=true}if(v!==false){let b=z;if(b.auto(o,Aa))zs();else Po(I,b.min,b.max);ai=ai||N.left>=0;gr=true;Yi()}}o.setData=Cc;function zs(){Aa=true;let s,v;if(r==1){if(Mt>0){mt=xn[0]=0;gt=xn[1]=Mt-1;s=t[0][mt];v=t[0][gt];if(ee==2){s=mt;v=gt}else if(s==v){if(ee==3)[s,v]=Ms(s,s,z.log,false);else if(ee==4)[s,v]=nc(s,s,z.log,false);else if(z.time)v=s+ut(86400/_);else[s,v]=Ls(s,v,lc,true)}}else{mt=xn[0]=s=null;gt=xn[1]=v=null}}Po(I,s,v)}let $n,Gi,Bs,Os,Ds,Es,Rs,Is,Ns;let Gt;function kc(s,v,b,y,$,V){s??=Y0;b??=cc;y??="butt";$??=Y0;V??="round";if(s!=$n)m.strokeStyle=$n=s;if($!=Gi)m.fillStyle=Gi=$;if(v!=Bs)m.lineWidth=Bs=v;if(V!=Ds)m.lineJoin=Ds=V;if(y!=Es)m.lineCap=Es=y;if(b!=Os)m.setLineDash(Os=b)}function Lc(s,v,b,y){if(v!=Gi)m.fillStyle=Gi=v;if(s!=Rs)m.font=Rs=s;if(b!=Is)m.textAlign=Is=b;if(y!=Ns)m.textBaseline=Ns=y}function js(s,v,b,y,$=0){if(y.length>0&&s.auto(o,Aa)&&(v==null||v.min==null)){let V=Pe(mt,0);let O=Pe(gt,y.length-1);let U=b.min==null?Z3(y,V,O,$,s.distr==3):[b.min,b.max];s.min=qr(s.min,b.min=U[0]);s.max=Ut(s.max,b.max=U[1])}}const xc={min:null,max:null};function Hh(){for(let y in D){let $=D[y];if(q[y]==null&&($.min==null||q[I]!=null&&$.auto(o,Aa))){q[y]=xc}}for(let y in D){let $=D[y];if(q[y]==null&&$.from!=null&&q[$.from]!=null)q[y]=xc}if(q[I]!=null)qi(true);let s={};for(let y in q){let $=q[y];if($!=null){let V=s[y]=La(D[y],I3);if($.min!=null)lt(V,$);else if(y!=I||r==2){if(Mt==0&&V.from==null){let O=V.range(o,null,null,y);V.min=O[0];V.max=O[1]}else{V.min=Ge;V.max=-Ge}}}}if(Mt>0){S.forEach((y,$)=>{if(r==1){let V=y.scale;let O=q[V];if(O==null)return;let U=s[V];if($==0){let G=U.range(o,U.min,U.max,V);U.min=G[0];U.max=G[1];mt=Gr(U.min,t[0]);gt=Gr(U.max,t[0]);if(gt-mt>1){if(t[0][mt]<U.min)mt++;if(t[0][gt]>U.max)gt--}y.min=Tr[mt];y.max=Tr[gt]}else if(y.show&&y.auto)js(U,O,y,t[$],y.sorted);y.idxs[0]=mt;y.idxs[1]=gt}else{if($>0){if(y.show&&y.auto){let[V,O]=y.facets;let U=V.scale;let G=O.scale;let[X,te]=t[$];let ae=s[U];let ge=s[G];ae!=null&&js(ae,q[U],V,X,V.sorted);ge!=null&&js(ge,q[G],O,te,O.sorted);y.min=O.min;y.max=O.max}}}});for(let y in s){let $=s[y];let V=q[y];if($.from==null&&(V==null||V.min==null)){let O=$.range(o,$.min==Ge?null:$.min,$.max==-Ge?null:$.max,y);$.min=O[0];$.max=O[1]}}}for(let y in s){let $=s[y];if($.from!=null){let V=s[$.from];if(V.min==null)$.min=$.max=null;else{let O=$.range(o,V.min,V.max,y);$.min=O[0];$.max=O[1]}}}let v={};let b=false;for(let y in s){let $=s[y];let V=D[y];if(V.min!=$.min||V.max!=$.max){V.min=$.min;V.max=$.max;let O=V.distr;V._min=O==3?_o(V.min):O==4?j1(V.min,V.asinh):O==100?V.fwd(V.min):V.min;V._max=O==3?_o(V.max):O==4?j1(V.max,V.asinh):O==100?V.fwd(V.max):V.max;v[y]=b=true}}if(b){S.forEach((y,$)=>{if(r==2){if($>0&&v.y)y._paths=null}else{if(v[y.scale])y._paths=null}});for(let y in v){Ni=true;wt("setScale",y)}if(we&&N.left>=0)ai=gr=true}for(let y in q)q[y]=null}function Sh(s){let v=K1(mt-1,0,Mt-1);let b=K1(gt+1,0,Mt-1);while(s[v]==null&&v>0)v--;while(s[b]==null&&b<Mt-1)b++;return[v,b]}function _h(){if(Mt>0){let s=S.some(v=>v._focus)&&Gt!=Qr.alpha;if(s)m.globalAlpha=Gt=Qr.alpha;S.forEach((v,b)=>{if(b>0&&v.show){$c(b,false);$c(b,true);if(v._paths==null){let y=Gt;if(Gt!=v.alpha)m.globalAlpha=Gt=v.alpha;let $=r==2?[0,t[b][0].length-1]:Sh(t[b]);v._paths=v.paths(o,b,$[0],$[1]);if(Gt!=y)m.globalAlpha=Gt=y}}});S.forEach((v,b)=>{if(b>0&&v.show){let y=Gt;if(Gt!=v.alpha)m.globalAlpha=Gt=v.alpha;v._paths!=null&&Mc(b,false);{let $=v._paths!=null?v._paths.gaps:null;let V=v.points.show(o,b,mt,gt,$);let O=v.points.filter(o,b,V,$);if(V||O){v.points._paths=v.points.paths(o,b,mt,gt,O);Mc(b,true)}}if(Gt!=y)m.globalAlpha=Gt=y;wt("drawSeries",b)}});if(s)m.globalAlpha=Gt=1}}function $c(s,v){let b=v?S[s].points:S[s];b._stroke=b.stroke(o,s);b._fill=b.fill(o,s)}function Mc(s,v){let b=v?S[s].points:S[s];let{stroke:y,fill:$,clip:V,flags:O,_stroke:U=b._stroke,_fill:G=b._fill,_width:X=b.width}=b._paths;X=qe(X*De,3);let te=null;let ae=X%2/2;if(v&&G==null)G=X>0?"#fff":U;let ge=b.pxAlign==1&&ae>0;ge&&m.translate(ae,ae);if(!v){let ze=tr-X/2,Ze=mr-X/2,xe=Wt+X,fe=Zr+X;te=new Path2D;te.rect(ze,Ze,xe,fe)}if(v)Fs(U,X,b.dash,b.cap,G,y,$,O,V);else Vh(s,U,X,b.dash,b.cap,G,y,$,O,te,V);ge&&m.translate(-ae,-ae)}function Vh(s,v,b,y,$,V,O,U,G,X,te){let ae=false;G!=0&&K.forEach((ge,ze)=>{if(ge.series[0]==s){let Ze=S[ge.series[1]];let xe=t[ge.series[1]];let fe=(Ze._paths||yn).band;if(Xo(fe))fe=ge.dir==1?fe[0]:fe[1];let le;let Xe=null;if(Ze.show&&fe&&P3(xe,mt,gt)){Xe=ge.fill(o,ze)||V;le=Ze._paths.clip}else fe=null;Fs(v,b,y,$,Xe,O,U,G,X,te,le,fe);ae=true}});if(!ae)Fs(v,b,y,$,V,O,U,G,X,te)}const Hc=xa|ec;function Fs(s,v,b,y,$,V,O,U,G,X,te,ae){kc(s,v,b,y,$);if(G||X||ae){m.save();G&&m.clip(G);X&&m.clip(X)}if(ae){if((U&Hc)==Hc){m.clip(ae);te&&m.clip(te);Hn($,O);Mn(s,V,v)}else if(U&ec){Hn($,O);m.clip(ae);Mn(s,V,v)}else if(U&xa){m.save();m.clip(ae);te&&m.clip(te);Hn($,O);m.restore();Mn(s,V,v)}}else{Hn($,O);Mn(s,V,v)}if(G||X||ae)m.restore()}function Mn(s,v,b){if(b>0){if(v instanceof Map){v.forEach((y,$)=>{m.strokeStyle=$n=$;m.stroke(y)})}else v!=null&&s&&m.stroke(v)}}function Hn(s,v){if(v instanceof Map){v.forEach((b,y)=>{m.fillStyle=Gi=y;m.fill(b)})}else v!=null&&s&&m.fill(v)}function Ah(s,v,b,y){let $=E[s];let V;if(y<=0)V=[0,0];else{let O=$._space=$.space(o,s,v,b,y);let U=$._incrs=$.incrs(o,s,v,b,y,O);V=tf(v,b,U,y,O)}return $._found=V}function Us(s,v,b,y,$,V,O,U,G,X){let te=O%2/2;A==1&&m.translate(te,te);kc(U,O,G,X,U);m.beginPath();let ae,ge,ze,Ze,xe=$+(y==0||y==3?-V:V);if(b==0){ge=$;Ze=xe}else{ae=$;ze=xe}for(let fe=0;fe<s.length;fe++){if(v[fe]!=null){if(b==0)ae=ze=s[fe];else ge=Ze=s[fe];m.moveTo(ae,ge);m.lineTo(ze,Ze)}}m.stroke();A==1&&m.translate(-te,-te)}function Zh(s){let v=true;E.forEach((b,y)=>{if(!b.show)return;let $=D[b.scale];if($.min==null){if(b._show){v=false;b._show=false;qi(false)}return}else{if(!b._show){v=false;b._show=true;qi(false)}}let V=b.side;let O=V%2;let{min:U,max:G}=$;let[X,te]=Ah(y,U,G,O==0?Ce:re);if(te==0)return;let ae=$.distr==2;let ge=b._splits=b.splits(o,y,U,G,X,te,ae);let ze=$.distr==2?ge.map(le=>Tr[le]):ge;let Ze=$.distr==2?Tr[ge[1]]-Tr[ge[0]]:X;let xe=b._values=b.values(o,b.filter(o,ze,y,te,Ze),y,te,Ze);b._rotate=V==2?b.rotate(o,xe,y,te):0;let fe=b._size;b._size=Ar(b.size(o,xe,y,s));if(fe!=null&&b._size!=fe)v=false});return v}function Th(s){let v=true;wc.forEach((b,y)=>{let $=b(o,y,li,s);if($!=Zo[y])v=false;Zo[y]=$});return v}function Ph(){for(let s=0;s<E.length;s++){let v=E[s];if(!v.show||!v._show)continue;let b=v.side;let y=b%2;let $,V;let O=v.stroke(o,s);let U=b==0||b==3?-1:1;let[G,X]=v._found;if(v.label!=null){let Rt=v.labelGap*U;let ir=ut((v._lpos+Rt)*De);Lc(v.labelFont[0],O,"center",b==2?un:q0);m.save();if(y==1){$=V=0;m.translate(ir,ut(mr+Zr/2));m.rotate((b==3?-Cs:Cs)/2)}else{$=ut(tr+Wt/2);V=ir}let di=O5(v.label)?v.label(o,s,G,X):v.label;m.fillText(di,$,V);m.restore()}if(X==0)continue;let te=D[v.scale];let ae=y==0?Wt:Zr;let ge=y==0?tr:mr;let ze=v._splits;let Ze=te.distr==2?ze.map(Rt=>Tr[Rt]):ze;let xe=te.distr==2?Tr[ze[1]]-Tr[ze[0]]:G;let fe=v.ticks;let le=v.border;let Xe=fe.show?fe.size:0;let tt=ut(Xe*De);let Ct=ut((v.alignTo==2?v._size-Xe-v.gap:v.gap)*De);let je=v._rotate*-Cs/180;let rt=H(v._pos*De);let rr=(tt+Ct)*U;let Et=rt+rr;V=y==0?Et:0;$=y==1?Et:0;let yr=v.font[0];let Pr=v.align==1?ba:v.align==2?R1:je>0?ba:je<0?R1:y==0?"center":b==3?R1:ba;let Jr=je||y==1?"middle":b==2?un:q0;Lc(yr,O,Pr,Jr);let or=v.font[1]*v.lineGap;let wr=ze.map(Rt=>H(p(Rt,te,ae,ge)));let zr=v._values;for(let Rt=0;Rt<zr.length;Rt++){let ir=zr[Rt];if(ir!=null){if(y==0)$=wr[Rt];else V=wr[Rt];ir=""+ir;let di=ir.indexOf("\n")==-1?[ir]:ir.split(/\n/gm);for(let It=0;It<di.length;It++){let Wc=di[It];if(je){m.save();m.translate($,V+It*or);m.rotate(je);m.fillText(Wc,0,0);m.restore()}else m.fillText(Wc,$,V+It*or)}}}if(fe.show){Us(wr,fe.filter(o,Ze,s,X,xe),y,b,rt,tt,qe(fe.width*De,3),fe.stroke(o,s),fe.dash,fe.cap)}let eo=v.grid;if(eo.show){Us(wr,eo.filter(o,Ze,s,X,xe),y,y==0?2:1,y==0?mr:tr,y==0?Zr:Wt,qe(eo.width*De,3),eo.stroke(o,s),eo.dash,eo.cap)}if(le.show){Us([rt],[1],y==0?1:0,y==0?1:2,y==1?mr:tr,y==1?Zr:Wt,qe(le.width*De,3),le.stroke(o,s),le.dash,le.cap)}}wt("drawAxes")}function qi(s){S.forEach((v,b)=>{if(b>0){v._paths=null;if(s){if(r==1){v.min=null;v.max=null}else{v.facets.forEach(y=>{y.min=null;y.max=null})}}}})}let Sn=false;let Ws=false;let Za=[];function zh(){Ws=false;for(let s=0;s<Za.length;s++)wt(...Za[s]);Za.length=0}function Yi(){if(!Sn){q3(Sc);Sn=true}}function Bh(s,v=false){Sn=true;Ws=v;s(o);Sc();if(v&&Za.length>0)queueMicrotask(zh)}o.batch=Bh;function Sc(){if(Ts){Hh();Ts=false}if(Ni){wh();Ni=false}if(kn){Je(M,ba,Ue);Je(M,un,st);Je(M,vn,Ce);Je(M,mn,re);Je(C,ba,Ue);Je(C,un,st);Je(C,vn,Ce);Je(C,mn,re);Je(u,vn,mo);Je(u,mn,ri);g.width=ut(mo*De);g.height=ut(ri*De);E.forEach(({_el:s,_show:v,_size:b,_pos:y,side:$})=>{if(s!=null){if(v){let V=$===3||$===0?b:0;let O=$%2==1;Je(s,O?"left":"top",y-V);Je(s,O?"width":"height",b);Je(s,O?"top":"left",O?st:Ue);Je(s,O?"height":"width",O?re:Ce);Y1(s,Pi)}else pr(s,Pi)}});$n=Gi=Bs=Ds=Es=Rs=Is=Ns=Os=null;Gt=1;za(true);if(Ue!=Ii||st!=oi||Ce!=Yr||re!=ii){qi(false);let s=Ce/Yr;let v=re/ii;if(we&&!ai&&N.left>=0){N.left*=s;N.top*=v;Qi&&vo(Qi,ut(N.left),0,Ce,re);Ki&&vo(Ki,0,ut(N.top),Ce,re);for(let b=0;b<br.length;b++){let y=br[b];if(y!=null){Ui[b]*=s;Wi[b]*=v;vo(y,Ar(Ui[b]),Ar(Wi[b]),Ce,re)}}}if(Ke.show&&!Ln&&Ke.left>=0&&Ke.width>0){Ke.left*=s;Ke.width*=s;Ke.top*=v;Ke.height*=v;for(let b in Xs)Je(ea,b,Ke[b])}Ii=Ue;oi=st;Yr=Ce;ii=re}wt("setSize");kn=false}if(mo>0&&ri>0){m.clearRect(0,0,g.width,g.height);wt("drawClear");R.forEach(s=>s());wt("draw")}if(Ke.show&&Ln){_n(Ke);Ln=false}if(we&&ai){ci(null,true,false);ai=false}if(W.show&&W.live&&gr){Qs();gr=false}if(!d){d=true;o.status=1;wt("ready")}Aa=false;Sn=false}o.redraw=(s,v)=>{Ni=v||false;if(s!==false)Po(I,z.min,z.max);else Yi()};function Gs(s,v){let b=D[s];if(b.from==null){if(Mt==0){let y=b.range(o,v.min,v.max,s);v.min=y[0];v.max=y[1]}if(v.min>v.max){let y=v.min;v.min=v.max;v.max=y}if(Mt>1&&v.min!=null&&v.max!=null&&v.max-v.min<1e-16)return;if(s==I){if(b.distr==2&&Mt>0){v.min=Gr(v.min,t[0]);v.max=Gr(v.max,t[0]);if(v.min==v.max)v.max++}}q[s]=v;Ts=true;Yi()}}o.setScale=Gs;let qs;let Ys;let Qi;let Ki;let _c;let Vc;let Xi;let Ji;let Ac;let Zc;let Qe;let et;let To=false;const Ht=N.drag;let bt=Ht.x;let yt=Ht.y;if(we){if(N.x)qs=Vr(b3,C);if(N.y)Ys=Vr(y3,C);if(z.ori==0){Qi=qs;Ki=Ys}else{Qi=Ys;Ki=qs}Qe=N.left;et=N.top}const Ke=o.select=lt({show:true,over:true,left:0,width:0,top:0,height:0},e.select);const ea=Ke.show?Vr(g3,Ke.over?C:M):null;function _n(s,v){if(Ke.show){for(let b in s){Ke[b]=s[b];if(b in Xs)Je(ea,b,s[b])}v!==false&&wt("setSelect")}}o.setSelect=_n;function Oh(s){let v=S[s];if(v.show)ye&&Y1(ne[s],Pi);else{ye&&pr(ne[s],Pi);if(we){let b=Fi?br[0]:br[s];b!=null&&vo(b,-10,-10,Ce,re)}}}function Po(s,v,b){Gs(s,{min:v,max:b})}function Kr(s,v,b,y){if(v.focus!=null)Nh(s);if(v.show!=null){S.forEach(($,V)=>{if(V>0&&(s==V||s==null)){$.show=v.show;Oh(V);if(r==2){Po($.facets[0].scale,null,null);Po($.facets[1].scale,null,null)}else Po($.scale,null,null);Yi()}})}b!==false&&wt("setSeries",s,v);y&&Ba("setSeries",o,s,v)}o.setSeries=Kr;function Dh(s,v){lt(K[s],v)}function Eh(s,v){s.fill=_e(s.fill||null);s.dir=Pe(s.dir,-1);v=v==null?K.length:v;K.splice(v,0,s)}function Rh(s){if(s==null)K.length=0;else K.splice(s,1)}o.addBand=Eh;o.setBand=Dh;o.delBand=Rh;function Ih(s,v){S[s].alpha=v;if(we&&br[s]!=null)br[s].style.opacity=v;if(ye&&ne[s])ne[s].style.opacity=v}let go;let zo;let si;const ta={focus:true};function Nh(s){if(s!=si){let v=s==null;let b=Qr.alpha!=1;S.forEach((y,$)=>{if(r==1||$>0){let V=v||$==0||$==s;y._focus=v?null:V;b&&Ih($,V?1:Qr.alpha)}});si=s;b&&Yi()}}if(ye&&ji){Dt(X0,ie,s=>{if(N._lock)return;ni(s);if(si!=null)Kr(null,ta,true,it.setSeries)})}function Xr(s,v,b){let y=D[v];if(b)s=s/De-(y.ori==1?st:Ue);let $=Ce;if(y.ori==1){$=re;s=$-s}if(y.dir==-1)s=$-s;let V=y._min,O=y._max,U=s/$;let G=V+(O-V)*U;let X=y.distr;return X==3?Ca(10,G):X==4?B3(G,y.asinh):X==100?y.bwd(G):G}function jh(s,v){let b=Xr(s,I,v);return Gr(b,t[0],mt,gt)}o.valToIdx=s=>Gr(s,t[0]);o.posToIdx=jh;o.posToVal=Xr;o.valToPos=(s,v,b)=>D[v].ori==0?a(s,D[v],b?Wt:Ce,b?tr:0):n(s,D[v],b?Zr:re,b?mr:0);o.setCursor=(s,v,b)=>{Qe=s.left;et=s.top;ci(null,v,b)};function Tc(s,v){Je(ea,ba,Ke.left=s);Je(ea,vn,Ke.width=v)}function Pc(s,v){Je(ea,un,Ke.top=s);Je(ea,mn,Ke.height=v)}let Ta=z.ori==0?Tc:Pc;let Pa=z.ori==1?Tc:Pc;function Fh(){if(ye&&W.live){for(let s=r==2?1:0;s<S.length;s++){if(s==0&&vr)continue;let v=W.values[s];let b=0;for(let y in v)er[s][b++].firstChild.nodeValue=v[y]}}}function Qs(s,v){if(s!=null){if(s.idxs){s.idxs.forEach((b,y)=>{ke[y]=b})}else if(!R3(s.idx))ke.fill(s.idx);W.idx=ke[0]}if(ye&&W.live){for(let b=0;b<S.length;b++){if(b>0||r==1&&!vr)Uh(b,ke[b])}Fh()}gr=false;v!==false&&wt("setLegend")}o.setLegend=Qs;function Uh(s,v){let b=S[s];let y=s==0&&ee==2?Tr:t[s];let $;if(vr)$=b.values(o,s,v)??Ao;else{$=b.value(o,v==null?null:y[v],s,v);$=$==null?Ao:{_:$}}W.values[s]=$}function ci(s,v,b){Ac=Qe;Zc=et;[Qe,et]=N.move(o,Qe,et);N.left=Qe;N.top=et;if(we){Qi&&vo(Qi,ut(Qe),0,Ce,re);Ki&&vo(Ki,0,ut(et),Ce,re)}let y;let $=mt>gt;go=Ge;zo=null;let V=z.ori==0?Ce:re;let O=z.ori==1?Ce:re;if(Qe<0||Mt==0||$){y=N.idx=null;for(let U=0;U<S.length;U++){let G=br[U];G!=null&&vo(G,-10,-10,Ce,re)}if(ji)Kr(null,ta,true,s==null&&it.setSeries);if(W.live){ke.fill(y);gr=true}}else{let U,G,X;if(r==1){U=z.ori==0?Qe:et;G=Xr(U,I);y=N.idx=Gr(G,t[0],mt,gt);X=T(t[0][y],z,V,0)}let te=-10;let ae=-10;let ge=0;let ze=0;let Ze=true;let xe="";let fe="";for(let le=r==2?1:0;le<S.length;le++){let Xe=S[le];let tt=ke[le];let Ct=tt==null?null:r==1?t[le][tt]:t[le][1][tt];let je=N.dataIdx(o,le,y,G);let rt=je==null?null:r==1?t[le][je]:t[le][1][je];gr=gr||rt!=Ct||je!=tt;ke[le]=je;if(le>0&&Xe.show){let rr=je==null?-10:je==y?X:T(r==1?t[0][je]:t[le][0][je],z,V,0);let Et=rt==null?-10:Z(rt,r==1?D[Xe.scale]:D[Xe.facets[1].scale],O,0);if(ji&&rt!=null){let yr=z.ori==1?Qe:et;let Pr=ft(Qr.dist(o,le,je,Et,yr));if(Pr<go){let Jr=Qr.bias;if(Jr!=0){let or=Xr(yr,Xe.scale);let wr=rt>=0?1:-1;let zr=or>=0?1:-1;if(zr==wr&&(zr==1?Jr==1?rt>=or:rt<=or:Jr==1?rt<=or:rt>=or)){go=Pr;zo=le}}else{go=Pr;zo=le}}}if(gr||Fi){let yr,Pr;if(z.ori==0){yr=rr;Pr=Et}else{yr=Et;Pr=rr}let Jr,or,wr,zr,eo,Rt,ir=true,di=At.bbox;if(di!=null){ir=false;let It=di(o,le);wr=It.left;zr=It.top;Jr=It.width;or=It.height}else{wr=yr;zr=Pr;Jr=or=At.size(o,le)}Rt=At.fill(o,le);eo=At.stroke(o,le);if(Fi){if(le==zo&&go<=Qr.prox){te=wr;ae=zr;ge=Jr;ze=or;Ze=ir;xe=Rt;fe=eo}}else{let It=br[le];if(It!=null){Ui[le]=wr;Wi[le]=zr;a5(It,Jr,or,ir);o5(It,Rt,eo);vo(It,Ar(wr),Ar(zr),Ce,re)}}}}}if(Fi){let le=Qr.prox;let Xe=si==null?go<=le:go>le||zo!=si;if(gr||Xe){let tt=br[0];if(tt!=null){Ui[0]=te;Wi[0]=ae;a5(tt,ge,ze,Ze);o5(tt,xe,fe);vo(tt,Ar(te),Ar(ae),Ce,re)}}}}if(Ke.show&&To){if(s!=null){let[U,G]=it.scales;let[X,te]=it.match;let[ae,ge]=s.cursor.sync.scales;let ze=s.cursor.drag;bt=ze._x;yt=ze._y;if(bt||yt){let{left:Ze,top:xe,width:fe,height:le}=s.select;let Xe=s.scales[ae].ori;let tt=s.posToVal;let Ct,je,rt,rr,Et;let yr=U!=null&&X(U,ae);let Pr=G!=null&&te(G,ge);if(yr&&bt){if(Xe==0){Ct=Ze;je=fe}else{Ct=xe;je=le}rt=D[U];rr=T(tt(Ct,ae),rt,V,0);Et=T(tt(Ct+je,ae),rt,V,0);Ta(qr(rr,Et),ft(Et-rr))}else Ta(0,V);if(Pr&&yt){if(Xe==1){Ct=Ze;je=fe}else{Ct=xe;je=le}rt=D[G];rr=Z(tt(Ct,ge),rt,O,0);Et=Z(tt(Ct+je,ge),rt,O,0);Pa(qr(rr,Et),ft(Et-rr))}else Pa(0,O)}else Js()}else{let U=ft(Ac-_c);let G=ft(Zc-Vc);if(z.ori==1){let ge=U;U=G;G=ge}bt=Ht.x&&U>=Ht.dist;yt=Ht.y&&G>=Ht.dist;let X=Ht.uni;if(X!=null){if(bt&&yt){bt=U>=X;yt=G>=X;if(!bt&&!yt){if(G>U)yt=true;else bt=true}}}else if(Ht.x&&Ht.y&&(bt||yt))bt=yt=true;let te,ae;if(bt){if(z.ori==0){te=Xi;ae=Qe}else{te=Ji;ae=et}Ta(qr(te,ae),ft(ae-te));if(!yt)Pa(0,O)}if(yt){if(z.ori==1){te=Xi;ae=Qe}else{te=Ji;ae=et}Pa(qr(te,ae),ft(ae-te));if(!bt)Ta(0,V)}if(!bt&&!yt){Ta(0,0);Pa(0,0)}}}Ht._x=bt;Ht._y=yt;if(s==null){if(b){if(Uc!=null){let[U,G]=it.scales;it.values[0]=U!=null?Xr(z.ori==0?Qe:et,U):null;it.values[1]=G!=null?Xr(z.ori==1?Qe:et,G):null}Ba(I1,o,Qe,et,Ce,re,y)}if(ji){let U=b&&it.setSeries;let G=Qr.prox;if(si==null){if(go<=G)Kr(zo,ta,true,U)}else{if(go>G)Kr(null,ta,true,U);else if(zo!=si)Kr(zo,ta,true,U)}}}if(gr){W.idx=y;Qs()}v!==false&&wt("setCursor")}let Bo=null;Object.defineProperty(o,"rect",{get(){if(Bo==null)za(false);return Bo}});function za(s=false){if(s)Bo=null;else{Bo=C.getBoundingClientRect();wt("syncRect",Bo)}}function zc(s,v,b,y,$,V,O){if(N._lock)return;if(To&&s!=null&&s.movementX==0&&s.movementY==0)return;Ks(s,v,b,y,$,V,O,false,s!=null);if(s!=null)ci(null,true,true);else ci(v,true,false)}function Ks(s,v,b,y,$,V,O,U,G){if(Bo==null)za(false);ni(s);if(s!=null){b=s.clientX-Bo.left;y=s.clientY-Bo.top}else{if(b<0||y<0){Qe=-10;et=-10;return}let[X,te]=it.scales;let ae=v.cursor.sync;let[ge,ze]=ae.values;let[Ze,xe]=ae.scales;let[fe,le]=it.match;let Xe=v.axes[0].side%2==1;let tt=z.ori==0?Ce:re,Ct=z.ori==1?Ce:re,je=Xe?V:$,rt=Xe?$:V,rr=Xe?y:b,Et=Xe?b:y;if(Ze!=null)b=fe(X,Ze)?p(ge,D[X],tt,0):-10;else b=tt*(rr/je);if(xe!=null)y=le(te,xe)?p(ze,D[te],Ct,0):-10;else y=Ct*(Et/rt);if(z.ori==1){let yr=b;b=y;y=yr}}if(G&&(v==null||v.cursor.event.type==I1)){if(b<=1||b>=Ce-1)b=Zi(b,Ce);if(y<=1||y>=re-1)y=Zi(y,re)}if(U){_c=b;Vc=y;[Xi,Ji]=N.move(o,b,y)}else{Qe=b;et=y}}const Xs={width:0,height:0,left:0,top:0};function Js(){_n(Xs,false)}let Bc;let Oc;let Dc;let Ec;function Rc(s,v,b,y,$,V,O){To=true;bt=yt=Ht._x=Ht._y=false;Ks(s,v,b,y,$,V,O,true,false);if(s!=null){Dt(N1,G1,Ic,false);Ba(Q0,o,Xi,Ji,Ce,re,null)}let{left:U,top:G,width:X,height:te}=Ke;Bc=U;Oc=G;Dc=X;Ec=te}function Ic(s,v,b,y,$,V,O){To=Ht._x=Ht._y=false;Ks(s,v,b,y,$,V,O,false,true);let{left:U,top:G,width:X,height:te}=Ke;let ae=X>0||te>0;let ge=Bc!=U||Oc!=G||Dc!=X||Ec!=te;ae&&ge&&_n(Ke);if(Ht.setScale&&ae&&ge){let ze=U,Ze=X,xe=G,fe=te;if(z.ori==1){ze=G,Ze=te,xe=U,fe=X}if(bt){Po(I,Xr(ze,I),Xr(ze+Ze,I))}if(yt){for(let le in D){let Xe=D[le];if(le!=I&&Xe.from==null&&Xe.min!=Ge){Po(le,Xr(xe+fe,le),Xr(xe,le))}}}Js()}else if(N.lock){N._lock=!N._lock;ci(v,true,s!=null)}if(s!=null){Ri(N1,G1);Ba(N1,o,Qe,et,Ce,re,null)}}function Wh(s,v,b,y,$,V,O){if(N._lock)return;ni(s);let U=To;if(To){let G=true;let X=true;let te=10;let ae,ge;if(z.ori==0){ae=bt;ge=yt}else{ae=yt;ge=bt}if(ae&&ge){G=Qe<=te||Qe>=Ce-te;X=et<=te||et>=re-te}if(ae&&G)Qe=Qe<Xi?0:Ce;if(ge&&X)et=et<Ji?0:re;ci(null,true,true);To=false}Qe=-10;et=-10;ke.fill(null);ci(null,true,true);if(U)To=U}function Nc(s,v,b,y,$,V,O){if(N._lock)return;ni(s);zs();Js();if(s!=null)Ba(J0,o,Qe,et,Ce,re,null)}function jc(){E.forEach(rf);Ps(o.width,o.height,true)}zi(ks,wa,jc);const ra={};ra.mousedown=Rc;ra.mousemove=zc;ra.mouseup=Ic;ra.dblclick=Nc;ra["setSeries"]=(s,v,b,y)=>{let $=it.match[2];b=$(o,v,b);b!=-1&&Kr(b,y,true,false)};if(we){Dt(Q0,C,Rc);Dt(I1,C,zc);Dt(K0,C,s=>{ni(s);za(false)});Dt(X0,C,Wh);Dt(J0,C,Nc);tc.add(o);o.syncRect=za}const Vn=o.hooks=e.hooks||{};function wt(s,v,b){if(Ws)Za.push([s,v,b]);else{if(s in Vn){Vn[s].forEach(y=>{y.call(null,o,v,b)})}}}(e.plugins||[]).forEach(s=>{for(let v in s.hooks)Vn[v]=(Vn[v]||[]).concat(s.hooks[v])});const Fc=(s,v,b)=>b;const it=lt({key:null,setSeries:false,filters:{pub:d5,sub:d5},scales:[I,S[1]?S[1].scale:null],match:[p5,p5,Fc],values:[null,null]},N.sync);if(it.match.length==2)it.match.push(Fc);N.sync=it;const Uc=it.key;const e1=lh(Uc);function Ba(s,v,b,y,$,V,O){if(it.filters.pub(s,v,b,y,$,V,O))e1.pub(s,v,b,y,$,V,O)}e1.sub(o);function Gh(s,v,b,y,$,V,O){if(it.filters.sub(s,v,b,y,$,V,O))ra[s](null,v,b,y,$,V,O)}o.pub=Gh;function qh(){e1.unsub(o);tc.delete(o);ti.clear();Q1(ks,wa,jc);f.remove();ie?.remove();wt("destroy")}o.destroy=qh;function t1(){wt("init",e,t);Cc(t||e.data,false);if(q[I])Gs(I,q[I]);else zs();Ln=Ke.show&&(Ke.width>0||Ke.height>0);ai=gr=true;Ps(e.width,e.height)}S.forEach(yc);E.forEach(Mh);if(i){if(i instanceof HTMLElement){i.appendChild(f);t1()}else i(o,t1)}else t1();return o}Vt.assign=lt;Vt.fmtNum=sc;Vt.rangeNum=Ls;Vt.rangeLog=Ms;Vt.rangeAsinh=nc;Vt.orient=Oi;Vt.pxRatio=De;{Vt.join=G3}{Vt.fmtDate=dc;Vt.tzDate=i6}Vt.sync=lh;{Vt.addGap=R6;Vt.clipGaps=_s;let e=Vt.paths={points:uh};e.linear=vh;e.stepped=j6;e.bars=F6;e.spline=W6}var of=Object.defineProperty;var af=Object.getOwnPropertyDescriptor;var Sa=(e,t,i,o)=>{var r=o>1?void 0:o?af(t,i):t;for(var a=e.length-1,n;a>=0;a--)if(n=e[a])r=(o?n(t,i,r):n(r))||r;if(o&&r)of(t,i,r);return r};var ei=class extends k{constructor(){super(...arguments);this.data=[[],[]];this.y=24;this.uplot=null}getCssColor(e){const t=getComputedStyle(this).getPropertyValue(e).trim();return t}firstUpdated(){const e={width:48,height:48,scales:{x:{time:false,show:false},y:{auto:true,show:false,range:(t,i,o,r)=>{const a=this.maxY??o-(this.minY??i);return[this.minY??i-a*.1,this.maxY??o+a*.1]}}},series:[{},{stroke:this.getCssColor("--element-neutral-color"),width:2,points:{show:false}}],axes:[{show:false},{ticks:{show:false},show:false,grid:{show:false}}],legend:{show:false},cursor:{show:false}};this.uplot=new Vt(e,this.data,this.chart);requestAnimationFrame(()=>this.updateY())}updatePalette(){if(!this.uplot){return}const e=this.getCssColor("--element-neutral-color");this.uplot.setSeries(1,{stroke:e,width:2,points:{show:false}})}updateY(){if(!this.uplot){return}const e=this.data[1][this.data[1].length-1];const t=this.uplot.scales.y.valToPct(e);this.y=t*32-3}updated(e){if(e.has("data")){this.updatePalette();this.uplot?.setData(this.data);requestAnimationFrame(()=>this.updateY())}}render(){return h`
      <div class="chart-container">
        <div id="chart"><div id="dot" style="bottom: ${this.y}px; "></div></div>
      </div>
    `}};ei.styles=Q(W0);Sa([l({type:Array})],ei.prototype,"data",2);Sa([l({type:Number})],ei.prototype,"minY",2);Sa([l({type:Number})],ei.prototype,"maxY",2);Sa([Do("#chart")],ei.prototype,"chart",2);Sa([Ve()],ei.prototype,"y",2);ei=Sa([x("obc-graph-mini")],ei);
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
lit-html/directives/repeat.js:
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
lit-html/directives/map.js:
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
