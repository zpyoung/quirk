(()=>{var MirrorValidator=()=>({checkValidity(element){let formControl=element.input,validity={message:"",isValid:!0,invalidKeys:[]};if(!formControl)return validity;let isValid=!0;if("checkValidity"in formControl&&(isValid=formControl.checkValidity()),isValid)return validity;if(validity.isValid=!1,"validationMessage"in formControl&&(validity.message=formControl.validationMessage),!("validity"in formControl))return validity.invalidKeys.push("customError"),validity;for(let key in formControl.validity){if(key==="valid")continue;let checkedKey=key;formControl.validity[checkedKey]&&validity.invalidKeys.push(checkedKey)}return validity}});var WaInvalidEvent=class extends Event{constructor(){super("wa-invalid",{bubbles:!0,cancelable:!1,composed:!0})}};var __defProp=Object.defineProperty,__getOwnPropDesc=Object.getOwnPropertyDescriptor,__typeError=msg=>{throw TypeError(msg)},__decorateClass=(decorators,target,key,kind)=>{for(var result=kind>1?void 0:kind?__getOwnPropDesc(target,key):target,i8=decorators.length-1,decorator;i8>=0;i8--)(decorator=decorators[i8])&&(result=(kind?decorator(target,key,result):decorator(result))||result);return kind&&result&&__defProp(target,key,result),result},__accessCheck=(obj,member,msg)=>member.has(obj)||__typeError("Cannot "+msg),__privateGet=(obj,member,getter)=>(__accessCheck(obj,member,"read from private field"),getter?getter.call(obj):member.get(obj)),__privateAdd=(obj,member,value)=>member.has(obj)?__typeError("Cannot add the same private member more than once"):member instanceof WeakSet?member.add(obj):member.set(obj,value),__privateSet=(obj,member,value,setter)=>(__accessCheck(obj,member,"write to private field"),setter?setter.call(obj,value):member.set(obj,value),value);var t=globalThis,e=t.ShadowRoot&&(t.ShadyCSS===void 0||t.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,s=Symbol(),o=new WeakMap,n=class{constructor(t6,e10,o10){if(this._$cssResult$=!0,o10!==s)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t6,this.t=e10}get styleSheet(){let t6=this.o,s4=this.t;if(e&&t6===void 0){let e10=s4!==void 0&&s4.length===1;e10&&(t6=o.get(s4)),t6===void 0&&((this.o=t6=new CSSStyleSheet).replaceSync(this.cssText),e10&&o.set(s4,t6))}return t6}toString(){return this.cssText}},r=t6=>new n(typeof t6=="string"?t6:t6+"",void 0,s),i=(t6,...e10)=>{let o10=t6.length===1?t6[0]:e10.reduce((e11,s4,o11)=>e11+(t7=>{if(t7._$cssResult$===!0)return t7.cssText;if(typeof t7=="number")return t7;throw Error("Value passed to 'css' function must be a 'css' function result: "+t7+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(s4)+t6[o11+1],t6[0]);return new n(o10,t6,s)},S=(s4,o10)=>{if(e)s4.adoptedStyleSheets=o10.map(t6=>t6 instanceof CSSStyleSheet?t6:t6.styleSheet);else for(let e10 of o10){let o11=document.createElement("style"),n6=t.litNonce;n6!==void 0&&o11.setAttribute("nonce",n6),o11.textContent=e10.cssText,s4.appendChild(o11)}},c=e?t6=>t6:t6=>t6 instanceof CSSStyleSheet?(t7=>{let e10="";for(let s4 of t7.cssRules)e10+=s4.cssText;return r(e10)})(t6):t6;var{is:i2,defineProperty:e2,getOwnPropertyDescriptor:h,getOwnPropertyNames:r2,getOwnPropertySymbols:o2,getPrototypeOf:n2}=Object,a=globalThis,c2=a.trustedTypes,l=c2?c2.emptyScript:"",p=a.reactiveElementPolyfillSupport,d=(t6,s4)=>t6,u={toAttribute(t6,s4){switch(s4){case Boolean:t6=t6?l:null;break;case Object:case Array:t6=t6==null?t6:JSON.stringify(t6)}return t6},fromAttribute(t6,s4){let i8=t6;switch(s4){case Boolean:i8=t6!==null;break;case Number:i8=t6===null?null:Number(t6);break;case Object:case Array:try{i8=JSON.parse(t6)}catch{i8=null}}return i8}},f=(t6,s4)=>!i2(t6,s4),b={attribute:!0,type:String,converter:u,reflect:!1,useDefault:!1,hasChanged:f};Symbol.metadata??=Symbol("metadata"),a.litPropertyMetadata??=new WeakMap;var y=class extends HTMLElement{static addInitializer(t6){this._$Ei(),(this.l??=[]).push(t6)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t6,s4=b){if(s4.state&&(s4.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t6)&&((s4=Object.create(s4)).wrapped=!0),this.elementProperties.set(t6,s4),!s4.noAccessor){let i8=Symbol(),h3=this.getPropertyDescriptor(t6,i8,s4);h3!==void 0&&e2(this.prototype,t6,h3)}}static getPropertyDescriptor(t6,s4,i8){let{get:e10,set:r8}=h(this.prototype,t6)??{get(){return this[s4]},set(t7){this[s4]=t7}};return{get:e10,set(s5){let h3=e10?.call(this);r8?.call(this,s5),this.requestUpdate(t6,h3,i8)},configurable:!0,enumerable:!0}}static getPropertyOptions(t6){return this.elementProperties.get(t6)??b}static _$Ei(){if(this.hasOwnProperty(d("elementProperties")))return;let t6=n2(this);t6.finalize(),t6.l!==void 0&&(this.l=[...t6.l]),this.elementProperties=new Map(t6.elementProperties)}static finalize(){if(this.hasOwnProperty(d("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(d("properties"))){let t7=this.properties,s4=[...r2(t7),...o2(t7)];for(let i8 of s4)this.createProperty(i8,t7[i8])}let t6=this[Symbol.metadata];if(t6!==null){let s4=litPropertyMetadata.get(t6);if(s4!==void 0)for(let[t7,i8]of s4)this.elementProperties.set(t7,i8)}this._$Eh=new Map;for(let[t7,s4]of this.elementProperties){let i8=this._$Eu(t7,s4);i8!==void 0&&this._$Eh.set(i8,t7)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(s4){let i8=[];if(Array.isArray(s4)){let e10=new Set(s4.flat(1/0).reverse());for(let s5 of e10)i8.unshift(c(s5))}else s4!==void 0&&i8.push(c(s4));return i8}static _$Eu(t6,s4){let i8=s4.attribute;return i8===!1?void 0:typeof i8=="string"?i8:typeof t6=="string"?t6.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t6=>this.enableUpdating=t6),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t6=>t6(this))}addController(t6){(this._$EO??=new Set).add(t6),this.renderRoot!==void 0&&this.isConnected&&t6.hostConnected?.()}removeController(t6){this._$EO?.delete(t6)}_$E_(){let t6=new Map,s4=this.constructor.elementProperties;for(let i8 of s4.keys())this.hasOwnProperty(i8)&&(t6.set(i8,this[i8]),delete this[i8]);t6.size>0&&(this._$Ep=t6)}createRenderRoot(){let t6=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return S(t6,this.constructor.elementStyles),t6}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t6=>t6.hostConnected?.())}enableUpdating(t6){}disconnectedCallback(){this._$EO?.forEach(t6=>t6.hostDisconnected?.())}attributeChangedCallback(t6,s4,i8){this._$AK(t6,i8)}_$ET(t6,s4){let i8=this.constructor.elementProperties.get(t6),e10=this.constructor._$Eu(t6,i8);if(e10!==void 0&&i8.reflect===!0){let h3=(i8.converter?.toAttribute!==void 0?i8.converter:u).toAttribute(s4,i8.type);this._$Em=t6,h3==null?this.removeAttribute(e10):this.setAttribute(e10,h3),this._$Em=null}}_$AK(t6,s4){let i8=this.constructor,e10=i8._$Eh.get(t6);if(e10!==void 0&&this._$Em!==e10){let t7=i8.getPropertyOptions(e10),h3=typeof t7.converter=="function"?{fromAttribute:t7.converter}:t7.converter?.fromAttribute!==void 0?t7.converter:u;this._$Em=e10;let r8=h3.fromAttribute(s4,t7.type);this[e10]=r8??this._$Ej?.get(e10)??r8,this._$Em=null}}requestUpdate(t6,s4,i8,e10=!1,h3){if(t6!==void 0){let r8=this.constructor;if(e10===!1&&(h3=this[t6]),i8??=r8.getPropertyOptions(t6),!((i8.hasChanged??f)(h3,s4)||i8.useDefault&&i8.reflect&&h3===this._$Ej?.get(t6)&&!this.hasAttribute(r8._$Eu(t6,i8))))return;this.C(t6,s4,i8)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t6,s4,{useDefault:i8,reflect:e10,wrapped:h3},r8){i8&&!(this._$Ej??=new Map).has(t6)&&(this._$Ej.set(t6,r8??s4??this[t6]),h3!==!0||r8!==void 0)||(this._$AL.has(t6)||(this.hasUpdated||i8||(s4=void 0),this._$AL.set(t6,s4)),e10===!0&&this._$Em!==t6&&(this._$Eq??=new Set).add(t6))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(t7){Promise.reject(t7)}let t6=this.scheduleUpdate();return t6!=null&&await t6,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[t8,s5]of this._$Ep)this[t8]=s5;this._$Ep=void 0}let t7=this.constructor.elementProperties;if(t7.size>0)for(let[s5,i8]of t7){let{wrapped:t8}=i8,e10=this[s5];t8!==!0||this._$AL.has(s5)||e10===void 0||this.C(s5,void 0,i8,e10)}}let t6=!1,s4=this._$AL;try{t6=this.shouldUpdate(s4),t6?(this.willUpdate(s4),this._$EO?.forEach(t7=>t7.hostUpdate?.()),this.update(s4)):this._$EM()}catch(s5){throw t6=!1,this._$EM(),s5}t6&&this._$AE(s4)}willUpdate(t6){}_$AE(t6){this._$EO?.forEach(t7=>t7.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t6)),this.updated(t6)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t6){return!0}update(t6){this._$Eq&&=this._$Eq.forEach(t7=>this._$ET(t7,this[t7])),this._$EM()}updated(t6){}firstUpdated(t6){}};y.elementStyles=[],y.shadowRootOptions={mode:"open"},y[d("elementProperties")]=new Map,y[d("finalized")]=new Map,p?.({ReactiveElement:y}),(a.reactiveElementVersions??=[]).push("2.1.2");var t2=globalThis,i3=t6=>t6,s2=t2.trustedTypes,e3=s2?s2.createPolicy("lit-html",{createHTML:t6=>t6}):void 0,h2="$lit$",o3=`lit$${Math.random().toFixed(9).slice(2)}$`,n3="?"+o3,r3=`<${n3}>`,l2=document,c3=()=>l2.createComment(""),a2=t6=>t6===null||typeof t6!="object"&&typeof t6!="function",u2=Array.isArray,d2=t6=>u2(t6)||typeof t6?.[Symbol.iterator]=="function",f2=`[ 	
\f\r]`,v=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,_=/-->/g,m=/>/g,p2=RegExp(`>|${f2}(?:([^\\s"'>=/]+)(${f2}*=${f2}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),g=/'/g,$=/"/g,y2=/^(?:script|style|textarea|title)$/i,x=t6=>(i8,...s4)=>({_$litType$:t6,strings:i8,values:s4}),b2=x(1),w=x(2),T=x(3),E=Symbol.for("lit-noChange"),A=Symbol.for("lit-nothing"),C=new WeakMap,P=l2.createTreeWalker(l2,129);function V(t6,i8){if(!u2(t6)||!t6.hasOwnProperty("raw"))throw Error("invalid template strings array");return e3!==void 0?e3.createHTML(i8):i8}var N=(t6,i8)=>{let s4=t6.length-1,e10=[],n6,l6=i8===2?"<svg>":i8===3?"<math>":"",c5=v;for(let i9=0;i9<s4;i9++){let s5=t6[i9],a4,u4,d3=-1,f3=0;for(;f3<s5.length&&(c5.lastIndex=f3,u4=c5.exec(s5),u4!==null);)f3=c5.lastIndex,c5===v?u4[1]==="!--"?c5=_:u4[1]!==void 0?c5=m:u4[2]!==void 0?(y2.test(u4[2])&&(n6=RegExp("</"+u4[2],"g")),c5=p2):u4[3]!==void 0&&(c5=p2):c5===p2?u4[0]===">"?(c5=n6??v,d3=-1):u4[1]===void 0?d3=-2:(d3=c5.lastIndex-u4[2].length,a4=u4[1],c5=u4[3]===void 0?p2:u4[3]==='"'?$:g):c5===$||c5===g?c5=p2:c5===_||c5===m?c5=v:(c5=p2,n6=void 0);let x2=c5===p2&&t6[i9+1].startsWith("/>")?" ":"";l6+=c5===v?s5+r3:d3>=0?(e10.push(a4),s5.slice(0,d3)+h2+s5.slice(d3)+o3+x2):s5+o3+(d3===-2?i9:x2)}return[V(t6,l6+(t6[s4]||"<?>")+(i8===2?"</svg>":i8===3?"</math>":"")),e10]},S2=class _S{constructor({strings:t6,_$litType$:i8},e10){let r8;this.parts=[];let l6=0,a4=0,u4=t6.length-1,d3=this.parts,[f3,v2]=N(t6,i8);if(this.el=_S.createElement(f3,e10),P.currentNode=this.el.content,i8===2||i8===3){let t7=this.el.content.firstChild;t7.replaceWith(...t7.childNodes)}for(;(r8=P.nextNode())!==null&&d3.length<u4;){if(r8.nodeType===1){if(r8.hasAttributes())for(let t7 of r8.getAttributeNames())if(t7.endsWith(h2)){let i9=v2[a4++],s4=r8.getAttribute(t7).split(o3),e11=/([.?@])?(.*)/.exec(i9);d3.push({type:1,index:l6,name:e11[2],strings:s4,ctor:e11[1]==="."?I:e11[1]==="?"?L:e11[1]==="@"?z:H}),r8.removeAttribute(t7)}else t7.startsWith(o3)&&(d3.push({type:6,index:l6}),r8.removeAttribute(t7));if(y2.test(r8.tagName)){let t7=r8.textContent.split(o3),i9=t7.length-1;if(i9>0){r8.textContent=s2?s2.emptyScript:"";for(let s4=0;s4<i9;s4++)r8.append(t7[s4],c3()),P.nextNode(),d3.push({type:2,index:++l6});r8.append(t7[i9],c3())}}}else if(r8.nodeType===8)if(r8.data===n3)d3.push({type:2,index:l6});else{let t7=-1;for(;(t7=r8.data.indexOf(o3,t7+1))!==-1;)d3.push({type:7,index:l6}),t7+=o3.length-1}l6++}}static createElement(t6,i8){let s4=l2.createElement("template");return s4.innerHTML=t6,s4}};function M(t6,i8,s4=t6,e10){if(i8===E)return i8;let h3=e10!==void 0?s4._$Co?.[e10]:s4._$Cl,o10=a2(i8)?void 0:i8._$litDirective$;return h3?.constructor!==o10&&(h3?._$AO?.(!1),o10===void 0?h3=void 0:(h3=new o10(t6),h3._$AT(t6,s4,e10)),e10!==void 0?(s4._$Co??=[])[e10]=h3:s4._$Cl=h3),h3!==void 0&&(i8=M(t6,h3._$AS(t6,i8.values),h3,e10)),i8}var R=class{constructor(t6,i8){this._$AV=[],this._$AN=void 0,this._$AD=t6,this._$AM=i8}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t6){let{el:{content:i8},parts:s4}=this._$AD,e10=(t6?.creationScope??l2).importNode(i8,!0);P.currentNode=e10;let h3=P.nextNode(),o10=0,n6=0,r8=s4[0];for(;r8!==void 0;){if(o10===r8.index){let i9;r8.type===2?i9=new k(h3,h3.nextSibling,this,t6):r8.type===1?i9=new r8.ctor(h3,r8.name,r8.strings,this,t6):r8.type===6&&(i9=new Z(h3,this,t6)),this._$AV.push(i9),r8=s4[++n6]}o10!==r8?.index&&(h3=P.nextNode(),o10++)}return P.currentNode=l2,e10}p(t6){let i8=0;for(let s4 of this._$AV)s4!==void 0&&(s4.strings!==void 0?(s4._$AI(t6,s4,i8),i8+=s4.strings.length-2):s4._$AI(t6[i8])),i8++}},k=class _k{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t6,i8,s4,e10){this.type=2,this._$AH=A,this._$AN=void 0,this._$AA=t6,this._$AB=i8,this._$AM=s4,this.options=e10,this._$Cv=e10?.isConnected??!0}get parentNode(){let t6=this._$AA.parentNode,i8=this._$AM;return i8!==void 0&&t6?.nodeType===11&&(t6=i8.parentNode),t6}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t6,i8=this){t6=M(this,t6,i8),a2(t6)?t6===A||t6==null||t6===""?(this._$AH!==A&&this._$AR(),this._$AH=A):t6!==this._$AH&&t6!==E&&this._(t6):t6._$litType$!==void 0?this.$(t6):t6.nodeType!==void 0?this.T(t6):d2(t6)?this.k(t6):this._(t6)}O(t6){return this._$AA.parentNode.insertBefore(t6,this._$AB)}T(t6){this._$AH!==t6&&(this._$AR(),this._$AH=this.O(t6))}_(t6){this._$AH!==A&&a2(this._$AH)?this._$AA.nextSibling.data=t6:this.T(l2.createTextNode(t6)),this._$AH=t6}$(t6){let{values:i8,_$litType$:s4}=t6,e10=typeof s4=="number"?this._$AC(t6):(s4.el===void 0&&(s4.el=S2.createElement(V(s4.h,s4.h[0]),this.options)),s4);if(this._$AH?._$AD===e10)this._$AH.p(i8);else{let t7=new R(e10,this),s5=t7.u(this.options);t7.p(i8),this.T(s5),this._$AH=t7}}_$AC(t6){let i8=C.get(t6.strings);return i8===void 0&&C.set(t6.strings,i8=new S2(t6)),i8}k(t6){u2(this._$AH)||(this._$AH=[],this._$AR());let i8=this._$AH,s4,e10=0;for(let h3 of t6)e10===i8.length?i8.push(s4=new _k(this.O(c3()),this.O(c3()),this,this.options)):s4=i8[e10],s4._$AI(h3),e10++;e10<i8.length&&(this._$AR(s4&&s4._$AB.nextSibling,e10),i8.length=e10)}_$AR(t6=this._$AA.nextSibling,s4){for(this._$AP?.(!1,!0,s4);t6!==this._$AB;){let s5=i3(t6).nextSibling;i3(t6).remove(),t6=s5}}setConnected(t6){this._$AM===void 0&&(this._$Cv=t6,this._$AP?.(t6))}},H=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t6,i8,s4,e10,h3){this.type=1,this._$AH=A,this._$AN=void 0,this.element=t6,this.name=i8,this._$AM=e10,this.options=h3,s4.length>2||s4[0]!==""||s4[1]!==""?(this._$AH=Array(s4.length-1).fill(new String),this.strings=s4):this._$AH=A}_$AI(t6,i8=this,s4,e10){let h3=this.strings,o10=!1;if(h3===void 0)t6=M(this,t6,i8,0),o10=!a2(t6)||t6!==this._$AH&&t6!==E,o10&&(this._$AH=t6);else{let e11=t6,n6,r8;for(t6=h3[0],n6=0;n6<h3.length-1;n6++)r8=M(this,e11[s4+n6],i8,n6),r8===E&&(r8=this._$AH[n6]),o10||=!a2(r8)||r8!==this._$AH[n6],r8===A?t6=A:t6!==A&&(t6+=(r8??"")+h3[n6+1]),this._$AH[n6]=r8}o10&&!e10&&this.j(t6)}j(t6){t6===A?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t6??"")}},I=class extends H{constructor(){super(...arguments),this.type=3}j(t6){this.element[this.name]=t6===A?void 0:t6}},L=class extends H{constructor(){super(...arguments),this.type=4}j(t6){this.element.toggleAttribute(this.name,!!t6&&t6!==A)}},z=class extends H{constructor(t6,i8,s4,e10,h3){super(t6,i8,s4,e10,h3),this.type=5}_$AI(t6,i8=this){if((t6=M(this,t6,i8,0)??A)===E)return;let s4=this._$AH,e10=t6===A&&s4!==A||t6.capture!==s4.capture||t6.once!==s4.once||t6.passive!==s4.passive,h3=t6!==A&&(s4===A||e10);e10&&this.element.removeEventListener(this.name,this,s4),h3&&this.element.addEventListener(this.name,this,t6),this._$AH=t6}handleEvent(t6){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t6):this._$AH.handleEvent(t6)}},Z=class{constructor(t6,i8,s4){this.element=t6,this.type=6,this._$AN=void 0,this._$AM=i8,this.options=s4}get _$AU(){return this._$AM._$AU}_$AI(t6){M(this,t6)}},j={M:h2,P:o3,A:n3,C:1,L:N,R,D:d2,V:M,I:k,H,N:L,U:z,B:I,F:Z},B=t2.litHtmlPolyfillSupport;B?.(S2,k),(t2.litHtmlVersions??=[]).push("3.3.3");var D=(t6,i8,s4)=>{let e10=s4?.renderBefore??i8,h3=e10._$litPart$;if(h3===void 0){let t7=s4?.renderBefore??null;e10._$litPart$=h3=new k(i8.insertBefore(c3(),t7),t7,void 0,s4??{})}return h3._$AI(t6),h3};var s3=globalThis,i4=class extends y{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t6=super.createRenderRoot();return this.renderOptions.renderBefore??=t6.firstChild,t6}update(t6){let r8=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t6),this._$Do=D(r8,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return E}};i4._$litElement$=!0,i4.finalized=!0,s3.litElementHydrateSupport?.({LitElement:i4});var o4=s3.litElementPolyfillSupport;o4?.({LitElement:i4});(s3.litElementVersions??=[]).push("4.2.2");var t3=t6=>(e10,o10)=>{o10!==void 0?o10.addInitializer(()=>{customElements.define(t6,e10)}):customElements.define(t6,e10)};var o5={attribute:!0,type:String,converter:u,reflect:!1,hasChanged:f},r4=(t6=o5,e10,r8)=>{let{kind:n6,metadata:i8}=r8,s4=globalThis.litPropertyMetadata.get(i8);if(s4===void 0&&globalThis.litPropertyMetadata.set(i8,s4=new Map),n6==="setter"&&((t6=Object.create(t6)).wrapped=!0),s4.set(r8.name,t6),n6==="accessor"){let{name:o10}=r8;return{set(r9){let n7=e10.get.call(this);e10.set.call(this,r9),this.requestUpdate(o10,n7,t6,!0,r9)},init(e11){return e11!==void 0&&this.C(o10,void 0,t6,e11),e11}}}if(n6==="setter"){let{name:o10}=r8;return function(r9){let n7=this[o10];e10.call(this,r9),this.requestUpdate(o10,n7,t6,!0,r9)}}throw Error("Unsupported decorator location: "+n6)};function n4(t6){return(e10,o10)=>typeof o10=="object"?r4(t6,e10,o10):((t7,e11,o11)=>{let r8=e11.hasOwnProperty(o11);return e11.constructor.createProperty(o11,t7),r8?Object.getOwnPropertyDescriptor(e11,o11):void 0})(t6,e10,o10)}function r5(r8){return n4({...r8,state:!0,attribute:!1})}var e4=(e10,t6,c5)=>(c5.configurable=!0,c5.enumerable=!0,Reflect.decorate&&typeof t6!="object"&&Object.defineProperty(e10,t6,c5),c5);function e5(e10,r8){return(n6,s4,i8)=>{let o10=t6=>t6.renderRoot?.querySelector(e10)??null;if(r8){let{get:e11,set:r9}=typeof s4=="object"?n6:i8??(()=>{let t6=Symbol();return{get(){return this[t6]},set(e12){this[t6]=e12}}})();return e4(n6,s4,{get(){let t6=e11.call(this);return t6===void 0&&(t6=o10(this),(t6!==null||this.hasUpdated)&&r9.call(this,t6)),t6}})}return e4(n6,s4,{get(){return o10(this)}})}}var host_styles_default=i`
  :host {
    box-sizing: border-box;
  }

  :host *,
  :host *::before,
  :host *::after {
    box-sizing: inherit;
  }

  [hidden],
  :host([hidden]) {
    display: none !important;
  }
`,HAS_ENDING_COLON=/;\s+$/;function camelToKebab(str){return str.replace(/[A-Z]/g,c5=>`-${c5.toLowerCase()}`)}function buildStyleAttribute(options){let{property:property2,value,element}=options;if(value){let style=element.getAttribute("style")||"";style&&(style.match(HAS_ENDING_COLON)||(style+=";"),style+=" ");let str=`${property2}: ${value}`;return style.includes(str)?void 0:`${style}${str};`}return null}var _hasRecordedInitialProperties,WebAwesomeElement=class extends i4{constructor(){super(),__privateAdd(this,_hasRecordedInitialProperties,!1),this.initialReflectedProperties=new Map,this.didSSR=!!this.shadowRoot,this.customStates={set:(customState,active)=>{if(this.internals?.states)try{active?this.internals.states.add(customState):this.internals.states.delete(customState)}catch(e10){if(String(e10).includes("must start with '--'"))console.error("Your browser implements an outdated version of CustomStateSet. Consider using a polyfill");else throw e10}},has:customState=>{if(!this.internals?.states)return!1;try{return this.internals.states.has(customState)}catch{return!1}}};try{this.internals=this.attachInternals()}catch{console.error("Element internals are not supported in your browser. Consider using a polyfill")}this.customStates.set("wa-defined",!0);let Self=this.constructor;for(let[property2,spec]of Self.elementProperties)spec.default==="inherit"&&spec.initial!==void 0&&typeof property2=="string"&&this.customStates.set(`initial-${property2}-${spec.initial}`,!0)}static get styles(){let styles=Array.isArray(this.css)?this.css:this.css?[this.css]:[];return[host_styles_default,...styles]}connectedCallback(){super.connectedCallback(),this.didSSR||this.shadowRoot?.prepend(document.createComment(` Web Awesome: https://webawesome.com/docs/components/${this.localName.replace("wa-","")} `)),this.didSSR&&this.updateComplete.then(()=>{this.shadowRoot?.prepend(document.createComment(` Web Awesome: https://webawesome.com/docs/components/${this.localName.replace("wa-","")} `))})}attributeChangedCallback(name,oldValue,newValue){__privateGet(this,_hasRecordedInitialProperties)||(this.constructor.elementProperties.forEach((obj,prop)=>{obj.reflect&&this[prop]!=null&&this.initialReflectedProperties.set(prop,this[prop])}),__privateSet(this,_hasRecordedInitialProperties,!0)),super.attributeChangedCallback(name,oldValue,newValue)}willUpdate(changedProperties){super.willUpdate(changedProperties),this.initialReflectedProperties.forEach((value,prop)=>{changedProperties.has(prop)&&this[prop]==null&&(this[prop]=value)})}firstUpdated(changedProperties){super.firstUpdated(changedProperties),this.didSSR&&this.shadowRoot?.querySelectorAll("slot").forEach(slotElement=>{slotElement.dispatchEvent(new Event("slotchange",{bubbles:!0,composed:!1,cancelable:!1}))})}update(changedProperties){try{super.update(changedProperties)}catch(e10){if(this.didSSR&&!this.hasUpdated){let event=new Event("lit-hydration-error",{bubbles:!0,composed:!0,cancelable:!1});event.error=e10,this.dispatchEvent(event)}throw e10}}setStyle(property2,value){if(!this.style){let str=buildStyleAttribute({property:camelToKebab(property2),value,element:this});str&&this.setAttribute("style",str);return}this.style[property2]=value}setStyleProperty(property2,value){if(!this.style){let str=buildStyleAttribute({property:property2,value,element:this});str&&this.setAttribute("style",str);return}this.style.setProperty(property2,value)}relayNativeEvent(event,eventOptions){event.stopImmediatePropagation(),this.dispatchEvent(new event.constructor(event.type,{...event,...eventOptions}))}};_hasRecordedInitialProperties=new WeakMap;__decorateClass([n4()],WebAwesomeElement.prototype,"dir",2);__decorateClass([n4()],WebAwesomeElement.prototype,"lang",2);__decorateClass([n4({type:Boolean,reflect:!0,attribute:"did-ssr"})],WebAwesomeElement.prototype,"didSSR",2);var CustomErrorValidator=()=>({observedAttributes:["custom-error"],checkValidity(element){let validity={message:"",isValid:!0,invalidKeys:[]};return element.customError&&(validity.message=element.customError,validity.isValid=!1,validity.invalidKeys=["customError"]),validity}}),WebAwesomeFormAssociatedElement=class extends WebAwesomeElement{constructor(){super(),this.name=null,this.disabled=!1,this.required=!1,this.assumeInteractionOn=["input"],this.validators=[],this.valueHasChanged=!1,this.hasInteracted=!1,this.customError=null,this.emittedEvents=[],this.emitInvalid=e10=>{e10.target===this&&(this.hasInteracted=!0,this.dispatchEvent(new WaInvalidEvent))},this.handleInteraction=event=>{let emittedEvents=this.emittedEvents;emittedEvents.includes(event.type)||emittedEvents.push(event.type),emittedEvents.length===this.assumeInteractionOn?.length&&(this.hasInteracted=!0)},"addEventListener"in this&&this.addEventListener("invalid",this.emitInvalid)}static get validators(){return[CustomErrorValidator()]}static get observedAttributes(){let parentAttrs=new Set(super.observedAttributes||[]);for(let validator of this.validators)if(validator.observedAttributes)for(let attr of validator.observedAttributes)parentAttrs.add(attr);return[...parentAttrs]}connectedCallback(){super.connectedCallback(),this.didSSR&&!this.hasUpdated?this.updateComplete.then(()=>{this.updateValidity()}):this.updateValidity(),this.assumeInteractionOn.forEach(event=>{this.addEventListener?.(event,this.handleInteraction)})}firstUpdated(...args){super.firstUpdated(...args),this.updateValidity()}willUpdate(changedProperties){if(!!1&&changedProperties.has("customError")&&(this.customError||(this.customError=null),this.setCustomValidity(this.customError||"")),changedProperties.has("value")||changedProperties.has("disabled")||changedProperties.has("defaultValue")){let value=this.value;this.updateFormValue(value)}changedProperties.has("disabled")&&(this.customStates.set("disabled",this.disabled),(this.hasAttribute("disabled")||!!1&&!this.matches(":disabled"))&&this.toggleAttribute("disabled",this.disabled)),super.willUpdate(changedProperties),this.didSSR&&!this.hasUpdated?this.updateComplete.then(()=>this.updateValidity()):this.updateValidity()}updateFormValue(value){if(Array.isArray(value)){if(this.name){let formData=new FormData;for(let val of value)formData.append(this.name,val);this.setValue(formData,formData)}}else this.setValue(value,value)}get labels(){return this.internals.labels}getForm(){return this.internals.form}set form(val){val?this.setAttribute("form",val):this.removeAttribute("form")}get form(){return this.internals.form}get validity(){return this.internals.validity}get willValidate(){return this.internals.willValidate}get validationMessage(){return this.internals.validationMessage}checkValidity(){return this.updateValidity(),this.internals.checkValidity()}reportValidity(){return this.updateValidity(),this.hasInteracted=!0,this.internals.reportValidity()}get validationTarget(){return this.input||void 0}setValidity(...args){let flags=args[0],message=args[1],anchor=args[2];anchor||(anchor=this.validationTarget),this.internals.setValidity(flags,message,anchor||void 0),this.requestUpdate("validity"),this.setCustomStates()}setCustomStates(){let required=!!this.required,isValid=this.internals.validity.valid,hasInteracted=this.hasInteracted;this.customStates.set("required",required),this.customStates.set("optional",!required),this.customStates.set("invalid",!isValid),this.customStates.set("valid",isValid),this.customStates.set("user-invalid",!isValid&&hasInteracted),this.customStates.set("user-valid",isValid&&hasInteracted)}setCustomValidity(message){if(!message){this.customError=null,this.setValidity({});return}this.customError=message,this.setValidity({customError:!0},message,this.validationTarget)}formResetCallback(){this.resetValidity(),this.hasInteracted=!1,this.valueHasChanged=!1,this.emittedEvents=[],this.updateValidity()}formDisabledCallback(isDisabled){this.disabled=isDisabled,this.updateValidity()}formStateRestoreCallback(state,reason){this.didSSR&&!this.hasUpdated?this.updateComplete.then(()=>{this.value=state,reason==="restore"&&this.resetValidity(),this.updateValidity()}):(this.value=state,reason==="restore"&&this.resetValidity(),this.updateValidity())}setValue(...args){let[value,state]=args;this.internals.setFormValue(value,state)}get allValidators(){let staticValidators=this.constructor.validators||[],validators=this.validators||[];return[...staticValidators,...validators]}resetValidity(){this.setCustomValidity(""),this.setValidity({})}updateValidity(){if(this.disabled||this.hasAttribute("disabled")||!this.willValidate){this.resetValidity();return}let validators=this.allValidators;if(!validators?.length)return;let flags={customError:!!this.customError},formControl=this.validationTarget||this.input||void 0,finalMessage="";for(let validator of validators){let{isValid,message,invalidKeys}=validator.checkValidity(this);isValid||(finalMessage||(finalMessage=message),invalidKeys?.length>=0&&invalidKeys.forEach(str=>flags[str]=!0))}finalMessage||(finalMessage=this.validationMessage),this.setValidity(flags,finalMessage,formControl)}};WebAwesomeFormAssociatedElement.formAssociated=!0;__decorateClass([n4({reflect:!0})],WebAwesomeFormAssociatedElement.prototype,"name",2);__decorateClass([n4({type:Boolean})],WebAwesomeFormAssociatedElement.prototype,"disabled",2);__decorateClass([n4({state:!0,attribute:!1})],WebAwesomeFormAssociatedElement.prototype,"valueHasChanged",2);__decorateClass([n4({state:!0,attribute:!1})],WebAwesomeFormAssociatedElement.prototype,"hasInteracted",2);__decorateClass([n4({attribute:"custom-error",reflect:!0})],WebAwesomeFormAssociatedElement.prototype,"customError",2);__decorateClass([n4({attribute:!1,state:!0,type:Object})],WebAwesomeFormAssociatedElement.prototype,"validity",1);var DEPRECATION_MAP={small:"s",medium:"m",large:"l"},warned=new Set;function warnDeprecatedSize(tagName,value){value in DEPRECATION_MAP&&!warned.has(`${tagName}:${value}`)&&(warned.add(`${tagName}:${value}`),console.warn(`[${tagName}] size="${value}" is deprecated. Use size="${DEPRECATION_MAP[value]}" instead. The long-form value will be removed in the next major version.`))}var HasSlotController=class{constructor(host,...slotNames){this.slotNames=[],this.handleSlotChange=event=>{let slot=event.target;(this.slotNames.includes("[default]")&&!slot.name||slot.name&&this.slotNames.includes(slot.name))&&this.host.requestUpdate()},(this.host=host).addController(this),this.slotNames=slotNames}hasDefaultSlot(){return this.host.childNodes?[...this.host.childNodes].some(node=>{if(node.nodeType===Node.TEXT_NODE&&node.textContent.trim()!=="")return!0;if(node.nodeType===Node.ELEMENT_NODE){let el=node;if(el.tagName.toLowerCase()==="wa-visually-hidden")return!1;if(!el.hasAttribute("slot"))return!0}return!1}):!1}hasNamedSlot(name){return this.host.querySelector?.(`:scope > [slot="${name}"]`)!==null}test(slotName,propertyName){return propertyName&&this.host.didSSR&&!this.host.hasUpdated?!!this.host[propertyName]:slotName==="[default]"?this.hasDefaultSlot():this.hasNamedSlot(slotName)}hostConnected(){let shadowRoot=this.host.shadowRoot;shadowRoot&&"addEventListener"in shadowRoot&&shadowRoot.addEventListener("slotchange",this.handleSlotChange)}hostDisconnected(){let shadowRoot=this.host.shadowRoot;shadowRoot&&"removeEventListener"in shadowRoot&&shadowRoot.removeEventListener("slotchange",this.handleSlotChange)}};var size_styles_default=i`
  :host([size='xs']) {
    font-size: var(--wa-font-size-xs);
  }

  :host([size='s']),
  :host([size='small']) {
    font-size: var(--wa-font-size-s);
  }

  :host([size='m']),
  :host([size='medium']) {
    font-size: var(--wa-font-size-m);
  }

  :host([size='l']),
  :host([size='large']) {
    font-size: var(--wa-font-size-l);
  }

  :host([size='xl']) {
    font-size: var(--wa-font-size-xl);
  }
`;var button_styles_default=i`
  @layer wa-component {
    :host {
      display: inline-block;

      /* Workaround because Chrome doesn't like :host(:has()) below
       * https://issues.chromium.org/issues/40062355
       * Firefox doesn't like this nested rule, so both are needed */
      &:has(wa-badge) {
        position: relative;
      }
    }

    /* Apply relative positioning only when needed to position wa-badge
     * This avoids creating a new stacking context for every button */
    :host(:has(wa-badge)) {
      position: relative;
    }
  }

  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none;
    user-select: none;
    -webkit-user-select: none;
    white-space: nowrap;
    vertical-align: middle;
    transition-property: background, border, box-shadow, color, opacity, transform;
    transition-duration: var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    transform-origin: center;
    cursor: pointer;
    padding: 0 var(--wa-form-control-padding-inline);
    font-family: inherit;
    font-size: inherit;
    font-weight: var(--wa-font-weight-action);
    height: var(--wa-form-control-height);
    width: 100%;

    background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));

    border-color: transparent;
    color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-form-control-border-radius));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-form-control-border-radius));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-form-control-border-radius));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-form-control-border-radius));
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
  }

  /* Hover and active transforms */
  .button:not(.disabled):not(.loading) {
    @media (hover: hover) {
      &:hover {
        transform: var(--wa-button-transform-hover);
      }
    }
    &:active {
      transform: var(--wa-button-transform-active);
    }

    @media (prefers-reduced-motion: reduce) {
      &:hover,
      &:active {
        transform: none;
      }
    }
  }

  /* Appearance modifiers */
  :host([appearance='plain']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
        background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='filled-outlined']) {
    /* Indentation overrides for grouping outlined */
    margin-inline-start: var(--_button-horizontal-indent-outlined);
    margin-block-start: var(--_button-vertical-indent-outlined);

    .button {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      color: var(--wa-color-on-normal, var(--wa-color-neutral-on-normal));
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-normal, var(--wa-color-neutral-fill-normal)),
        var(--wa-color-mix-active)
      );
    }
  }

  :host([appearance='accent']) {
    /* Indentation overrides for grouping */
    margin-inline-start: var(--_button-horizontal-indent);
    margin-block-start: var(--_button-vertical-indent);

    .button {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
    @media (hover: hover) {
      .button:not(.disabled):not(.loading):hover {
        background-color: color-mix(
          in oklab,
          var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
          var(--wa-color-mix-hover)
        );
      }
    }
    .button:not(.disabled):not(.loading):active {
      background-color: color-mix(
        in oklab,
        var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud)),
        var(--wa-color-mix-active)
      );
    }
  }

  /* Focus states */
  .button:focus {
    outline: none;
  }

  .button:focus-visible {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled state */
  :host([disabled]) {
    opacity: 0.5;
    cursor: not-allowed;

    /* When disabled, prevent mouse events from bubbling up from children */
    .button {
      pointer-events: none;
    }
  }

  /* Keep it last so Safari doesn't stop parsing this block */
  .button::-moz-focus-inner {
    border: 0;
  }

  /* Icon buttons */
  .button.is-icon-button {
    outline-offset: 2px;
    width: var(--wa-form-control-height);
    aspect-ratio: 1;
  }

  /* Icon buttons with a caret need to grow to fit both the icon and the caret */
  .button.is-icon-button.caret {
    width: auto;
    aspect-ratio: auto;
    min-width: var(--wa-form-control-height);
  }

  /* Pill modifier */
  :host([pill]) .button {
    border-start-start-radius: var(--_button-start-start-radius, var(--wa-border-radius-pill));
    border-start-end-radius: var(--_button-start-end-radius, var(--wa-border-radius-pill));
    border-end-start-radius: var(--_button-end-start-radius, var(--wa-border-radius-pill));
    border-end-end-radius: var(--_button-end-end-radius, var(--wa-border-radius-pill));
  }

  /*
   * Label
   */

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    pointer-events: none;
  }

  .label {
    display: inline-block;
  }

  .is-icon-button .label {
    display: flex;
    justify-content: center;
  }

  .label::slotted(wa-icon) {
    align-self: center;
  }

  /*
   * Caret modifier
   */

  wa-icon[part='caret'] {
    display: flex;
    align-self: center;
    align-items: center;

    &::part(svg) {
      width: 0.875em;
      height: 0.875em;
    }

    .button:has(&) .end {
      display: none;
    }
  }

  /*
   * Loading modifier
   */

  .loading {
    position: relative;
    cursor: wait;

    .start,
    .label,
    .end,
    .caret {
      /* Hidden with opacity, not visibility, so the label stays in the accessibility tree */
      opacity: 0;

      /* Unlike visibility: hidden, opacity leaves the content clickable */
      pointer-events: none;
    }

    wa-spinner {
      --indicator-color: currentColor;
      --track-color: color-mix(in oklab, currentColor, transparent 90%);

      position: absolute;
      font-size: 1em;
      height: 1em;
      width: 1em;
      top: calc(50% - 0.5em);
      left: calc(50% - 0.5em);
    }
  }

  /*
   * Badges
   */

  .button ::slotted(wa-badge) {
    border-color: var(--wa-color-surface-default);
    position: absolute;
    inset-block-start: 0;
    inset-inline-end: 0;
    translate: 50% -50%;
    pointer-events: none;
  }

  :host(:dir(rtl)) ::slotted(wa-badge) {
    translate: -50% -50%;
  }

  /*
  * Button spacing
  */

  slot[name='start']::slotted(*) {
    margin-inline-end: 0.75em;
  }

  slot[name='end']::slotted(*),
  .button:not(.visually-hidden-label) [part='caret'] {
    margin-inline-start: 0.75em;
  }
`;var variants_styles_default=i`
  :where(:root),
  .wa-neutral,
  :host([variant='neutral']) {
    --wa-color-fill-loud: var(--wa-color-neutral-fill-loud);
    --wa-color-fill-normal: var(--wa-color-neutral-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-neutral-fill-quiet);
    --wa-color-border-loud: var(--wa-color-neutral-border-loud);
    --wa-color-border-normal: var(--wa-color-neutral-border-normal);
    --wa-color-border-quiet: var(--wa-color-neutral-border-quiet);
    --wa-color-on-loud: var(--wa-color-neutral-on-loud);
    --wa-color-on-normal: var(--wa-color-neutral-on-normal);
    --wa-color-on-quiet: var(--wa-color-neutral-on-quiet);
  }

  .wa-brand,
  :host([variant='brand']) {
    --wa-color-fill-loud: var(--wa-color-brand-fill-loud);
    --wa-color-fill-normal: var(--wa-color-brand-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-brand-fill-quiet);
    --wa-color-border-loud: var(--wa-color-brand-border-loud);
    --wa-color-border-normal: var(--wa-color-brand-border-normal);
    --wa-color-border-quiet: var(--wa-color-brand-border-quiet);
    --wa-color-on-loud: var(--wa-color-brand-on-loud);
    --wa-color-on-normal: var(--wa-color-brand-on-normal);
    --wa-color-on-quiet: var(--wa-color-brand-on-quiet);
  }

  .wa-success,
  :host([variant='success']) {
    --wa-color-fill-loud: var(--wa-color-success-fill-loud);
    --wa-color-fill-normal: var(--wa-color-success-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-success-fill-quiet);
    --wa-color-border-loud: var(--wa-color-success-border-loud);
    --wa-color-border-normal: var(--wa-color-success-border-normal);
    --wa-color-border-quiet: var(--wa-color-success-border-quiet);
    --wa-color-on-loud: var(--wa-color-success-on-loud);
    --wa-color-on-normal: var(--wa-color-success-on-normal);
    --wa-color-on-quiet: var(--wa-color-success-on-quiet);
  }

  .wa-warning,
  :host([variant='warning']) {
    --wa-color-fill-loud: var(--wa-color-warning-fill-loud);
    --wa-color-fill-normal: var(--wa-color-warning-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-warning-fill-quiet);
    --wa-color-border-loud: var(--wa-color-warning-border-loud);
    --wa-color-border-normal: var(--wa-color-warning-border-normal);
    --wa-color-border-quiet: var(--wa-color-warning-border-quiet);
    --wa-color-on-loud: var(--wa-color-warning-on-loud);
    --wa-color-on-normal: var(--wa-color-warning-on-normal);
    --wa-color-on-quiet: var(--wa-color-warning-on-quiet);
  }

  .wa-danger,
  :host([variant='danger']) {
    --wa-color-fill-loud: var(--wa-color-danger-fill-loud);
    --wa-color-fill-normal: var(--wa-color-danger-fill-normal);
    --wa-color-fill-quiet: var(--wa-color-danger-fill-quiet);
    --wa-color-border-loud: var(--wa-color-danger-border-loud);
    --wa-color-border-normal: var(--wa-color-danger-border-normal);
    --wa-color-border-quiet: var(--wa-color-danger-border-quiet);
    --wa-color-on-loud: var(--wa-color-danger-on-loud);
    --wa-color-on-normal: var(--wa-color-danger-on-normal);
    --wa-color-on-quiet: var(--wa-color-danger-on-quiet);
  }
`;function watch(propertyName,options){let resolvedOptions={waitUntilFirstUpdate:!1,...options};return(proto,decoratedFnName)=>{let{update:update2}=proto,watchedProperties=Array.isArray(propertyName)?propertyName:[propertyName];proto.update=function(changedProps){watchedProperties.forEach(property=>{let key=property;if(changedProps.has(key)){let oldValue=changedProps.get(key),newValue=this[key];oldValue!==newValue&&(!resolvedOptions.waitUntilFirstUpdate||this.hasUpdated)&&this[decoratedFnName](oldValue,newValue)}}),update2.call(this,changedProps)}}}var connectedElements=new Set,translations=new Map,fallback,documentDirection="ltr",documentLanguage="en",isClient=typeof MutationObserver<"u"&&typeof document<"u"&&typeof document.documentElement<"u";if(isClient){let documentElementObserver=new MutationObserver(update);documentDirection=document.documentElement.dir||"ltr",documentLanguage=document.documentElement.lang||navigator.language,documentElementObserver.observe(document.documentElement,{attributes:!0,attributeFilter:["dir","lang"]})}function registerTranslation(...translation2){translation2.map(t6=>{let code=t6.$code.toLowerCase();translations.has(code)?translations.set(code,Object.assign(Object.assign({},translations.get(code)),t6)):translations.set(code,t6),fallback||(fallback=t6)}),update()}function update(){isClient&&(documentDirection=document.documentElement.dir||"ltr",documentLanguage=document.documentElement.lang||navigator.language),[...connectedElements.keys()].map(el=>{typeof el.requestUpdate=="function"&&el.requestUpdate()})}var LocalizeController=class{constructor(host){this.host=host,this.host.addController(this)}hostConnected(){connectedElements.add(this.host)}hostDisconnected(){connectedElements.delete(this.host)}dir(){return`${this.host.dir||documentDirection}`.toLowerCase()}lang(){let lang=`${this.host.lang||documentLanguage}`.toLowerCase().replace(/_/g,"-");try{return new Intl.Locale(lang),lang}catch{return fallback?fallback.$code.toLowerCase():"en"}}getTranslationData(lang){var _a,_b;let locale;try{locale=new Intl.Locale(lang.replace(/_/g,"-"))}catch{return{locale:void 0,language:"",region:"",primary:void 0,secondary:void 0}}let language=locale.language.toLowerCase(),region=(_b=(_a=locale.region)===null||_a===void 0?void 0:_a.toLowerCase())!==null&&_b!==void 0?_b:"",primary=translations.get(`${language}-${region}`),secondary=translations.get(language);return{locale,language,region,primary,secondary}}exists(key,options){var _a;let{primary,secondary}=this.getTranslationData((_a=options.lang)!==null&&_a!==void 0?_a:this.lang());return options=Object.assign({includeFallback:!1},options),!!(primary&&primary[key]||secondary&&secondary[key]||options.includeFallback&&fallback&&fallback[key])}term(key,...args){let{primary,secondary}=this.getTranslationData(this.lang()),term;if(primary&&primary[key])term=primary[key];else if(secondary&&secondary[key])term=secondary[key];else if(fallback&&fallback[key])term=fallback[key];else return console.error(`No translation found for: ${String(key)}`),String(key);return typeof term=="function"?term(...args):term}date(dateToFormat,options){return dateToFormat=new Date(dateToFormat),new Intl.DateTimeFormat(this.lang(),options).format(dateToFormat)}number(numberToFormat,options){return numberToFormat=Number(numberToFormat),isNaN(numberToFormat)?"":new Intl.NumberFormat(this.lang(),options).format(numberToFormat)}relativeTime(value,unit,options){return new Intl.RelativeTimeFormat(this.lang(),options).format(value,unit)}};var translation={$code:"en",$name:"English",$dir:"ltr",allTagsRemoved:"All tags removed",am:"AM",autosizeColumn:"Autosize column",captions:"Captions",carousel:"Carousel",chooseDate:"Choose date",chooseDecade:"Choose decade",chooseMonth:"Choose month",chooseTime:"Choose time",chooseYear:"Choose year",clearEntry:"Clear entry",clearFilter:"Clear filter",clearSort:"Clear sort",close:"Close",closeCalendar:"Close calendar",closeTimeInput:"Close time picker",collapseRow:"Collapse row",columnMenu:"Column options",columnMovedToPosition:(label,position,total)=>`${label} moved to position ${position} of ${total}`,columns:"Columns",compactPageXOfY:(page,total)=>`${page} of ${total}`,completed:"Completed",copied:"Copied",copy:"Copy",createOption:value=>`Create "${value}"`,currentlyPlaying:"currently playing",currentValue:"Current value",date:"Date",datePickerKeyboardHelp:"Use arrow keys to change values; press Alt+Down Arrow to open the calendar.",day:"Day",dayPeriod:"AM/PM",decrement:"Decrement",deselectAllRows:"Deselect all rows",disabled:"Disabled",dropFileHere:"Drop file here or click to browse",dropFilesHere:"Drop files here or click to browse",empty:"Empty",endDate:"End date",enterFullscreen:"Enter fullscreen",error:"Error",exitFullscreen:"Exit fullscreen",expandRow:"Expand row",filterByColumn:label=>`Filter by ${label}`,filterFrom:"From",filterMax:"Max",filterMin:"Min",filterTo:"To",firstPage:"First page",goToSlide:(slide,count)=>`Go to slide ${slide} of ${count}`,hideColumn:"Hide column",hidePassword:"Hide password",hour:"Hour",incompleteDate:"Enter a valid date.",increment:"Increment",jumpBackwardX:count=>`Jump back ${count} pages`,jumpForwardX:count=>`Jump forward ${count} pages`,lastPage:"Last page",loading:"Loading",locked:"Locked",minute:"Minute",month:"Month",moreOptions:"More Options",mute:"Mute",nextDecade:"Next decade",nextMonth:"Next month",nextPage:"Next page",nextSlide:"Next slide",nextVideo:"Next Video",nextYear:"Next year",noData:"No data",noOptions:"No options",noResults:"No matching results",notCompleted:"Not completed",now:"Now",numCharacters:num=>num===1?"1 character":`${num} characters`,numCharactersRemaining:num=>num===1?"1 character remaining":`${num} characters remaining`,numOptionsAvailable:num=>num===0?"No options available":num===1?"1 option available":`${num} options available`,numOptionsSelected:num=>num===0?"No options selected":num===1?"1 option selected":`${num} options selected`,numRowsCopied:num=>num===1?"1 row copied":`${num} rows copied`,numRowsSelected:num=>num===1?"1 row selected":`${num} rows selected`,optionPosition:(label,position,total)=>`${label}, ${position} of ${total}`,optionsLoadError:"Options could not be loaded",pageXOfY:(page,total)=>`Page ${page} of ${total}`,pagination:"Pagination",pause:"Pause",pauseAnimation:"Pause animation",pictureInPicture:"Picture in picture",pinLeft:"Pin left",pinRight:"Pin right",play:"Play",playAnimation:"Play animation",playbackSpeed:"Playback speed",playlist:"Playlist",pm:"PM",previousDecade:"Previous decade",previousMonth:"Previous month",previousPage:"Previous page",previousSlide:"Previous slide",previousVideo:"Previous video",previousYear:"Previous year",progress:"Progress",rangeTooLong:max2=>max2===1?"Select a range no longer than 1 day":`Select a range no longer than ${max2} days`,rangeTooShort:min2=>min2===1?"Select a range at least 1 day long":`Select a range at least ${min2} days long`,readonly:"Read-only",remove:"Remove",resetColumns:"Reset columns",resize:"Resize",resizeColumn:"Resize column",rowsPerPage:"Rows per page",scrollableRegion:"Scrollable region",scrollToEnd:"Scroll to end",scrollToStart:"Scroll to start",search:"Search",second:"Second",seek:"Seek",seekProgress:(current,duration)=>`${current} of ${duration}`,selectAColorFromTheScreen:"Select a color from the screen",selectAllRows:"Select all rows",selected:"Selected",selectedDateLabel:date=>`Selected: ${date}`,selectedRangeLabel:range=>`Selected range: ${range}`,selectGroup:"Select group",selectionCleared:"Selection cleared",selectRow:"Select row",showingNofMRows:(shown,total)=>`Showing ${shown} of ${total} rows`,showingXtoYofZ:(start,end,total)=>`${start}\u2013${end} of ${total}`,showPassword:"Show password",slideNum:slide=>`Slide ${slide}`,sortAscending:"Sort ascending",sortColumn:"Sort column",sortDescending:"Sort descending",startDate:"Start date",steps:"Steps",stepXOfY:(step,total)=>`Step ${step} of ${total}`,tagAdded:tag=>`${tag} added`,tagAlreadyAdded:tag=>`${tag} is already added`,tagInputKeyboardHelp:"Press Backspace or Delete to remove this tag.",tagRemoved:tag=>`${tag} removed`,time:"Time",timeInputKeyboardHelp:"Use arrow keys to change values; press Alt+Down Arrow to open the time picker.",today:"Today",toggleColorFormat:"Toggle color format",tooFewTags:min2=>min2===1?"Add at least 1 tag":`Add at least ${min2} tags`,tooManyTags:max2=>max2===1?"Add no more than 1 tag":`Add no more than ${max2} tags`,unmute:"Unmute",unpin:"Unpin",unpinColumn:"Unpin column",videoPlayer:"Video player",volume:"Volume",year:"Year",zoomIn:"Zoom in",zoomOut:"Zoom out"};registerTranslation(translation);var en_default=translation;var LocalizeController2=class extends LocalizeController{lang(){return this.host.didSSR&&!this.host.hasUpdated?this.host.lang||"en":super.lang()}};registerTranslation(en_default);var t4={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},e6=t6=>(...e10)=>({_$litDirective$:t6,values:e10}),i5=class{constructor(t6){}get _$AU(){return this._$AM._$AU}_$AT(t6,e10,i8){this._$Ct=t6,this._$AM=e10,this._$Ci=i8}_$AS(t6,e10){return this.update(t6,e10)}update(t6,e10){return this.render(...e10)}};var e7=e6(class extends i5{constructor(t6){if(super(t6),t6.type!==t4.ATTRIBUTE||t6.name!=="class"||t6.strings?.length>2)throw Error("`classMap()` can only be used in the `class` attribute and must be the only part in the attribute.")}render(t6){return" "+Object.keys(t6).filter(s4=>t6[s4]).join(" ")+" "}update(s4,[i8]){if(this.st===void 0){this.st=new Set,s4.strings!==void 0&&(this.nt=new Set(s4.strings.join(" ").split(/\s/).filter(t6=>t6!=="")));for(let t6 in i8)i8[t6]&&!this.nt?.has(t6)&&this.st.add(t6);return this.render(i8)}let r8=s4.element.classList;for(let t6 of this.st)t6 in i8||(r8.remove(t6),this.st.delete(t6));for(let t6 in i8){let s5=!!i8[t6];s5===this.st.has(t6)||this.nt?.has(t6)||(s5?(r8.add(t6),this.st.add(t6)):(r8.remove(t6),this.st.delete(t6)))}return E}});var o7=o10=>o10??A;var a3=Symbol.for(""),o8=t6=>{if(t6?.r===a3)return t6?._$litStatic$};var i6=(t6,...r8)=>({_$litStatic$:r8.reduce((r9,e10,a4)=>r9+(t7=>{if(t7._$litStatic$!==void 0)return t7._$litStatic$;throw Error(`Value passed to 'literal' function must be a 'literal' result: ${t7}. Use 'unsafeStatic' to pass non-literal values, but
            take care to ensure page security.`)})(e10)+t6[a4+1],t6[0]),r:a3}),l3=new Map,n5=t6=>(r8,...e10)=>{let a4=e10.length,s4,i8,n6=[],u4=[],c5,$3=0,f3=!1;for(;$3<a4;){for(c5=r8[$3];$3<a4&&(i8=e10[$3],(s4=o8(i8))!==void 0);)c5+=s4+r8[++$3],f3=!0;$3!==a4&&u4.push(i8),n6.push(c5),$3++}if($3===a4&&n6.push(r8[a4]),f3){let t7=n6.join("$$lit$$");(r8=l3.get(t7))===void 0&&(n6.raw=n6,l3.set(t7,r8=n6)),e10=u4}return t6(r8,...e10)},u3=n5(b2),c4=n5(w),$2=n5(T);var WaButton=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.assumeInteractionOn=["click"],this.hasSlotController=new HasSlotController(this,"[default]","start","end"),this.localize=new LocalizeController2(this),this.invalid=!1,this.isIconButton=!1,this.title="",this.variant="neutral",this.appearance="accent",this.size="m",this.withCaret=!1,this.withStart=!1,this.withEnd=!1,this.disabled=!1,this.loading=!1,this.pill=!1,this.type="button"}static get validators(){return[...super.validators,MirrorValidator()]}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}constructLightDOMButton(){let button=document.createElement("button");for(let attribute of this.attributes)attribute.name!=="style"&&button.setAttribute(attribute.name,attribute.value);return button.type=this.type,button.style.position="absolute !important",button.style.width="0 !important",button.style.height="0 !important",button.style.clipPath="inset(50%) !important",button.style.overflow="hidden !important",button.style.whiteSpace="nowrap !important",this.name&&(button.name=this.name),button.value=this.value||"",button}handleClick(event){if(this.disabled||this.loading){event.preventDefault(),event.stopImmediatePropagation();return}if(this.type!=="submit"&&this.type!=="reset"||!this.getForm())return;let lightDOMButton=this.constructLightDOMButton();this.parentElement?.append(lightDOMButton),lightDOMButton.click(),lightDOMButton.remove()}handleInvalid(){this.dispatchEvent(new WaInvalidEvent)}handleLabelSlotChange(){let nodes=this.labelSlot.assignedNodes({flatten:!0}),hasIconLabel=!1,hasIcon=!1,hasText=!1,hasOtherElements=!1;[...nodes].forEach(node=>{if(node.nodeType===Node.ELEMENT_NODE){let element=node;element.localName==="wa-icon"?(hasIcon=!0,hasIconLabel||(hasIconLabel=element.label!==void 0)):hasOtherElements=!0}else node.nodeType===Node.TEXT_NODE&&(node.textContent?.trim()||"").length>0&&(hasText=!0)}),this.isIconButton=hasIcon&&!hasText&&!hasOtherElements,this.customStates.set("icon-button",this.isIconButton),this.isIconButton&&!hasIconLabel&&console.warn('Icon buttons must have a label for screen readers. Add <wa-icon label="..."> to remove this warning.',this)}isButton(){return!this.href}isLink(){return!!this.href}handleDisabledChange(){this.customStates.set("disabled",this.disabled),this.updateValidity()}handleHrefChange(){this.customStates.set("link",this.isLink())}handleLoadingChange(){this.customStates.set("loading",this.loading)}setValue(..._args){}click(){this.button.click()}focus(options){this.button.focus(options)}blur(){this.button.blur()}render(){let isLink=this.isLink(),tag=isLink?i6`a`:i6`button`;return u3`
      <${tag}
        part="base button"
        class=${e7({button:!0,caret:this.withCaret,disabled:this.disabled,loading:this.loading,rtl:this.localize.dir()==="rtl","has-label":this.hasSlotController.test("[default]"),"has-start":this.hasSlotController.test("start","withStart"),"has-end":this.hasSlotController.test("end","withEnd"),"is-icon-button":this.isIconButton})}
        ?disabled=${o7(isLink?void 0:this.disabled)}
        type=${o7(isLink?void 0:this.type)}
        title=${this.title}
        name=${o7(isLink?void 0:this.name)}
        value=${o7(isLink?void 0:this.value)}
        href=${o7(isLink?this.href:void 0)}
        target=${o7(isLink?this.target:void 0)}
        download=${o7(isLink?this.download:void 0)}
        rel=${o7(isLink&&this.rel?this.rel:void 0)}
        role=${o7(isLink?void 0:"button")}
        aria-disabled=${o7(isLink&&this.disabled?"true":void 0)}
        aria-busy=${this.loading?"true":"false"}
        tabindex=${this.disabled?"-1":"0"}
        @invalid=${this.isButton()?this.handleInvalid:null}
        @click=${this.handleClick}
      >
        <slot name="start" part="start" class="start"></slot>
        <slot part="label" class="label" @slotchange=${this.handleLabelSlotChange}></slot>
        <slot name="end" part="end" class="end"></slot>
        ${this.withCaret?u3`
                <wa-icon part="caret" class="caret" library="system" name="chevron-down" variant="solid"></wa-icon>
              `:""}
        ${this.loading?u3`<wa-spinner part="spinner"></wa-spinner>`:""}
      </${tag}>
    `}};WaButton.shadowRootOptions={...WebAwesomeFormAssociatedElement.shadowRootOptions,delegatesFocus:!0};WaButton.css=[button_styles_default,variants_styles_default,size_styles_default];__decorateClass([e5(".button")],WaButton.prototype,"button",2);__decorateClass([e5("slot:not([name])")],WaButton.prototype,"labelSlot",2);__decorateClass([r5()],WaButton.prototype,"invalid",2);__decorateClass([r5()],WaButton.prototype,"isIconButton",2);__decorateClass([n4()],WaButton.prototype,"title",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"variant",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"appearance",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"size",2);__decorateClass([watch("size")],WaButton.prototype,"handleSizeChange",1);__decorateClass([n4({attribute:"with-caret",type:Boolean,reflect:!0})],WaButton.prototype,"withCaret",2);__decorateClass([n4({attribute:"with-start",type:Boolean})],WaButton.prototype,"withStart",2);__decorateClass([n4({attribute:"with-end",type:Boolean})],WaButton.prototype,"withEnd",2);__decorateClass([n4({type:Boolean})],WaButton.prototype,"disabled",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaButton.prototype,"loading",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaButton.prototype,"pill",2);__decorateClass([n4()],WaButton.prototype,"type",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"name",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"value",2);__decorateClass([n4({reflect:!0})],WaButton.prototype,"href",2);__decorateClass([n4()],WaButton.prototype,"target",2);__decorateClass([n4()],WaButton.prototype,"rel",2);__decorateClass([n4()],WaButton.prototype,"download",2);__decorateClass([n4({attribute:"formaction"})],WaButton.prototype,"formAction",2);__decorateClass([n4({attribute:"formenctype"})],WaButton.prototype,"formEnctype",2);__decorateClass([n4({attribute:"formmethod"})],WaButton.prototype,"formMethod",2);__decorateClass([n4({attribute:"formnovalidate",type:Boolean})],WaButton.prototype,"formNoValidate",2);__decorateClass([n4({attribute:"formtarget"})],WaButton.prototype,"formTarget",2);__decorateClass([watch("disabled",{waitUntilFirstUpdate:!0})],WaButton.prototype,"handleDisabledChange",1);__decorateClass([watch("href")],WaButton.prototype,"handleHrefChange",1);__decorateClass([watch("loading",{waitUntilFirstUpdate:!0})],WaButton.prototype,"handleLoadingChange",1);WaButton=__decorateClass([t3("wa-button")],WaButton);WaButton.disableWarning?.("change-in-update");var spinner_styles_default=i`
  :host {
    --track-width: 2px;
    --track-color: var(--wa-color-neutral-fill-normal);
    --indicator-color: var(--wa-color-brand-fill-loud);
    --speed: 2s;
    --size: 1em;

    /*
      Resizing a spinner element using anything but font-size will break the animation because the animation uses em
      units. Therefore, if a spinner is used in a flex container without \`flex: none\` applied, the spinner can
      grow/shrink and break the animation. The use of \`flex: none\` on the host element prevents this by always having
      the spinner sized according to its actual dimensions.
    */
    flex: none;
    display: inline-flex;
    width: var(--size);
    height: var(--size);
  }

  svg {
    width: 100%;
    height: 100%;
    aspect-ratio: 1;
    animation: spin var(--speed) linear infinite;
  }

  .track,
  .indicator {
    --radius: calc(var(--size) / 2 - var(--track-width) / 2);
    --circumference: calc(var(--radius) * 2 * 3.141592654);

    cx: calc(var(--size) / 2);
    cy: calc(var(--size) / 2);
    r: var(--radius);
    fill: none;
    stroke-width: var(--track-width);
  }

  .track {
    stroke: var(--track-color);
  }

  .indicator {
    stroke: var(--indicator-color);
    stroke-linecap: round;
    stroke-dasharray: calc(0.597 * var(--circumference)), calc(0.796 * var(--circumference));
    stroke-dashoffset: calc(-0.04 * var(--circumference));
    animation: dash 1.5s ease-in-out infinite;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes dash {
    0% {
      stroke-dasharray: calc(0.008 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: 0;
    }
    50% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.278 * var(--circumference));
    }
    100% {
      stroke-dasharray: calc(0.716 * var(--circumference)), calc(1.194 * var(--circumference));
      stroke-dashoffset: calc(-0.987 * var(--circumference));
    }
  }
`;var WaSpinner=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this)}render(){return b2`
      <svg
        part="base spinner"
        role="progressbar"
        aria-label=${this.localize.term("loading")}
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <circle class="track" />
        <circle class="indicator" />
      </svg>
    `}};WaSpinner.css=spinner_styles_default;WaSpinner=__decorateClass([t3("wa-spinner")],WaSpinner);var WaErrorEvent=class extends Event{constructor(){super("wa-error",{bubbles:!0,cancelable:!1,composed:!0})}};var WaLoadEvent=class extends Event{constructor(){super("wa-load",{bubbles:!0,cancelable:!1,composed:!0})}};var icon_styles_default=i`
  :host {
    --primary-color: currentColor;
    --primary-opacity: 1;
    --secondary-color: currentColor;
    --secondary-opacity: 0.4;
    --rotate-angle: 0deg;

    box-sizing: content-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    vertical-align: -0.125em;
  }

  /* #region Canvas — the box the icon is centered within (mirrors Font Awesome's icon canvas). Orthogonal to font-size. */

  /* Fixed width (default): 1.25em × 1em (20 × 16px) */
  :host(:not([canvas])),
  :host([canvas='fixed']) {
    width: 1.25em;
    height: 1em;
    min-width: 1.25em; /* <-- this is what Safari respects for intrinsic */
    min-height: 1em;
  }

  /* Auto: hug the icon's width. \`auto-width\` is the deprecated alias for canvas="auto". */
  :host([canvas='auto']),
  :host([auto-width]:not([canvas])) {
    width: auto;
    height: 1em;
  }

  /* Square: 1.25em × 1.25em (20 × 20px) */
  :host([canvas='square']) {
    width: 1.25em;
    height: 1.25em;
    min-width: 1.25em;
    min-height: 1.25em;
  }

  /* Roomy: 1.5em × 1.5em (24 × 24px) */
  :host([canvas='roomy']) {
    width: 1.5em;
    height: 1.5em;
    min-width: 1.5em;
    min-height: 1.5em;
  }

  /* #endregion */

  svg {
    /* NOTE: Avoid setting fill here. A stylesheet rule beats SVG presentation attributes, breaking stroke-based
       libraries like Lucide (fill="none" stroke="currentColor") and attribute-based mutators (issue #1733). The default
       library applies fill="currentColor" in its mutator instead. */
    height: 1em;
    overflow: visible;
    width: auto;

    /* Duotone colors with path-specific opacity fallback */
    path[data-duotone-primary] {
      color: var(--primary-color);
      opacity: var(--path-opacity, var(--primary-opacity));
    }

    path[data-duotone-secondary] {
      color: var(--secondary-color);
      opacity: var(--path-opacity, var(--secondary-opacity));
    }
  }

  /* Rotation */
  :host([rotate]) {
    transform: rotate(var(--rotate-angle, 0deg));
  }

  /* Flipping */
  :host([flip='x']) {
    transform: scaleX(-1);
  }
  :host([flip='y']) {
    transform: scaleY(-1);
  }
  :host([flip='both']) {
    transform: scale(-1, -1);
  }

  /* Rotation and Flipping combined */
  :host([rotate][flip='x']) {
    transform: rotate(var(--rotate-angle, 0deg)) scaleX(-1);
  }
  :host([rotate][flip='y']) {
    transform: rotate(var(--rotate-angle, 0deg)) scaleY(-1);
  }
  :host([rotate][flip='both']) {
    transform: rotate(var(--rotate-angle, 0deg)) scale(-1, -1);
  }

  /* #region Animations — ported from Font Awesome 7.3 (--fa-* props mapped to wa-icon's --* names) */

  :host([animation='beat']) {
    animation-name: beat;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='bounce']) {
    animation-name: bounce;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, cubic-bezier(0.28, 0.84, 0.42, 1));
  }

  :host([animation='fade']) {
    animation-name: fade;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='beat-fade']) {
    animation-name: beat-fade;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='flip']) {
    animation-name: flip;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1.5s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='flip-360']) {
    animation-name: flip-360;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='shake']) {
    animation-name: shake;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.75s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
  }

  :host([animation='spin']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-pulse']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, steps(8));
  }

  /* spin-reverse is FA's reverse modifier expressed as a standalone value; reverse any spin via --animation-direction: reverse */
  :host([animation='spin-reverse']) {
    animation-name: spin;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, reverse);
    animation-duration: var(--animation-duration, 2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap']) {
    animation-name: spin-snap;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 3s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap-4']) {
    animation-name: spin-snap-4;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 2.4s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='spin-snap-8']) {
    animation-name: spin-snap-8;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 4s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='buzz']) {
    animation-name: buzz;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.6s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, linear);
  }

  :host([animation='wag']) {
    animation-name: wag;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.9s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
    transform-origin: bottom center;
  }

  :host([animation='float']) {
    animation-name: float;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 3s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-in-out);
    will-change: transform;
  }

  :host([animation='swing']) {
    animation-name: swing;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 1.2s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
    transform-origin: top center;
  }

  :host([animation='jello']) {
    animation-name: jello;
    animation-delay: var(--animation-delay, 0s);
    animation-direction: var(--animation-direction, normal);
    animation-duration: var(--animation-duration, 0.9s);
    animation-iteration-count: var(--animation-iteration-count, infinite);
    animation-timing-function: var(--animation-timing, ease-out);
  }

  @media (prefers-reduced-motion: reduce) {
    :host([animation='beat']),
    :host([animation='bounce']),
    :host([animation='fade']),
    :host([animation='beat-fade']),
    :host([animation='flip']),
    :host([animation='flip-360']),
    :host([animation='shake']),
    :host([animation='spin']),
    :host([animation='spin-pulse']),
    :host([animation='spin-reverse']),
    :host([animation='spin-snap']),
    :host([animation='spin-snap-4']),
    :host([animation='spin-snap-8']),
    :host([animation='buzz']),
    :host([animation='wag']),
    :host([animation='float']),
    :host([animation='swing']),
    :host([animation='jello']) {
      animation: none !important;
      transition: none !important;
    }
  }

  /* #endregion */

  /* #region Keyframes — ported verbatim from Font Awesome 7.3 */

  @keyframes beat {
    0% {
      transform: scale(1);
    }
    25% {
      transform: scale(calc(1.25 * var(--beat-scale, 1.25)));
    }
    45% {
      transform: scale(calc(1.22 * var(--beat-scale, 1.22)));
    }
    65% {
      transform: scale(calc(1.25 * var(--beat-scale, 1.25)));
    }
    90% {
      transform: scale(1);
    }
  }

  @keyframes bounce {
    0% {
      transform: scale(1, 1) translateY(0);
      /* No fallback by design (ported from FA 7.3): the first segment uses the user's --animation-timing or the CSS
         initial ease, while the explicit cubic-beziers on later stops drive the bounce physics. */
      animation-timing-function: var(--animation-timing);
    }
    14% {
      transform: scale(var(--bounce-start-scale-x, 1.06), var(--bounce-start-scale-y, 0.94))
        translateY(var(--bounce-anticipation, 3px));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    32% {
      transform: scale(var(--bounce-jump-scale-x, 0.94), var(--bounce-jump-scale-y, 1.12))
        translateY(calc(-1 * var(--bounce-height, 0.5em)));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    52% {
      transform: scale(1, 1) translateY(calc(-1 * var(--bounce-height, 0.5em) * 1.1));
      animation-timing-function: cubic-bezier(0.5, 0, 1, 0.5);
    }
    70% {
      transform: scale(var(--bounce-land-scale-x, 1.06), var(--bounce-land-scale-y, 0.92)) translateY(0);
      animation-timing-function: cubic-bezier(0.33, 0.33, 0.66, 1);
    }
    85% {
      transform: scale(0.98, 1.04) translateY(calc(-2px * var(--bounce-rebound, 1)));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: scale(1, 1) translateY(0);
    }
  }

  @keyframes fade {
    0% {
      opacity: 1;
      transform: scale(1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    40% {
      opacity: var(--fade-opacity, 0.4);
      transform: scale(0.98);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    100% {
      opacity: 1;
      transform: scale(1);
    }
  }

  @keyframes beat-fade {
    0% {
      opacity: var(--beat-fade-opacity, 0.4);
      transform: scale(1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    25% {
      opacity: calc(var(--beat-fade-opacity, 0.4) + 0.4);
      transform: scale(var(--beat-fade-scale, 1.28));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    45% {
      opacity: 1;
      transform: scale(var(--beat-fade-scale, 1.25));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    65% {
      opacity: calc(var(--beat-fade-opacity, 0.4) + 0.4);
      transform: scale(var(--beat-fade-scale, 1.28));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    100% {
      opacity: var(--beat-fade-opacity, 0.4);
      transform: scale(1);
    }
  }

  @keyframes flip {
    0% {
      transform: perspective(2em) scale(1) rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    8% {
      transform: perspective(2em) scale(var(--flip-anticipation-scale, 0.95))
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    35% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.6));
      animation-timing-function: linear;
    }
    65% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.5));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    92% {
      transform: perspective(2em) scale(1)
        rotate3d(
          var(--flip-x, 0),
          var(--flip-y, 1),
          var(--flip-z, 0),
          calc(var(--flip-angle, -360deg) * var(--flip-overshoot, 1.04))
        );
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), var(--flip-angle, -360deg));
    }
  }

  @keyframes flip-360 {
    0% {
      transform: perspective(2em) scale(1) rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.4, 1);
    }
    8% {
      transform: perspective(2em) scale(var(--flip-anticipation-scale, 0.95))
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), 0deg);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    50% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), calc(var(--flip-angle, -360deg) * 0.6));
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    80% {
      transform: perspective(2em) scale(1)
        rotate3d(
          var(--flip-x, 0),
          var(--flip-y, 1),
          var(--flip-z, 0),
          calc(var(--flip-angle, -360deg) * var(--flip-overshoot, 1.04))
        );
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: perspective(2em) scale(1)
        rotate3d(var(--flip-x, 0), var(--flip-y, 1), var(--flip-z, 0), var(--flip-angle, -360deg));
    }
  }

  @keyframes shake {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    8% {
      transform: rotate(35deg) translateX(1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    20% {
      transform: rotate(-22deg) translateX(-1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    35% {
      transform: rotate(15deg) translateX(1px);
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    50% {
      transform: rotate(-9deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    65% {
      transform: rotate(5deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    78% {
      transform: rotate(-3deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    90% {
      transform: rotate(1deg);
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    12% {
      transform: rotate(60deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    16.67% {
      transform: rotate(60deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    28.67% {
      transform: rotate(120deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    33.33% {
      transform: rotate(120deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    45.33% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    62% {
      transform: rotate(240deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    66.67% {
      transform: rotate(240deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    78.67% {
      transform: rotate(300deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    83.33% {
      transform: rotate(300deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    95.33% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap-4 {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    15% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    25% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    40% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    65% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    75% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    90% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes spin-snap-8 {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    9% {
      transform: rotate(45deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    12.5% {
      transform: rotate(45deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    21.5% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    25% {
      transform: rotate(90deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    34% {
      transform: rotate(135deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    37.5% {
      transform: rotate(135deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    46.5% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    50% {
      transform: rotate(180deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    59% {
      transform: rotate(225deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    62.5% {
      transform: rotate(225deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    71.5% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    75% {
      transform: rotate(270deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    84% {
      transform: rotate(315deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    87.5% {
      transform: rotate(315deg);
      animation-timing-function: cubic-bezier(0, 0, 0.2, 1);
    }
    96.5% {
      transform: rotate(360deg);
      animation-timing-function: cubic-bezier(0.8, 0, 1, 1);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  @keyframes buzz {
    0% {
      transform: translateX(0) rotate(0deg);
      animation-timing-function: cubic-bezier(0.1, 0, 0.9, 1);
    }
    5% {
      transform: translateX(var(--buzz-distance, 4px)) rotate(0.5deg);
    }
    10% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px))) rotate(-0.5deg);
    }
    15% {
      transform: translateX(var(--buzz-distance, 4px)) rotate(0.3deg);
    }
    20% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px))) rotate(-0.3deg);
    }
    25% {
      transform: translateX(calc(var(--buzz-distance, 4px) * 0.7)) rotate(0.2deg);
    }
    30% {
      transform: translateX(calc(-1 * var(--buzz-distance, 4px) * 0.7)) rotate(-0.2deg);
    }
    35% {
      transform: translateX(calc(var(--buzz-distance, 4px) * 0.4)) rotate(0.1deg);
    }
    40% {
      transform: translateX(0) rotate(0deg);
    }
    100% {
      transform: translateX(0) rotate(0deg);
    }
  }

  @keyframes wag {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    12% {
      transform: rotate(var(--wag-angle, 12deg));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    24% {
      transform: rotate(2deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    36% {
      transform: rotate(calc(var(--wag-angle, 12deg) * 0.85));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    48% {
      transform: rotate(1deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.6, 1);
    }
    58% {
      transform: rotate(calc(var(--wag-angle, 12deg) * 0.6));
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    68% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes float {
    0% {
      transform: translateY(0) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    15% {
      transform: translateY(calc(-0.4 * var(--float-height, 6px))) translateX(var(--float-drift, 1px))
        rotate(var(--float-tilt, 1deg)) scale(1, 1);
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    35% {
      transform: translateY(calc(-1 * var(--float-height, 6px))) translateX(0) rotate(0deg)
        scale(var(--float-stretch-x, 0.98), var(--float-stretch-y, 1.03));
      animation-timing-function: cubic-bezier(0.5, 0, 0.5, 0);
    }
    50% {
      transform: translateY(calc(-0.92 * var(--float-height, 6px))) translateX(calc(-0.5 * var(--float-drift, 1px)))
        rotate(calc(-0.5 * var(--float-tilt, 1deg))) scale(0.995, 1.01);
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 0.33);
    }
    70% {
      transform: translateY(calc(-0.3 * var(--float-height, 6px))) translateX(calc(-1 * var(--float-drift, 1px)))
        rotate(calc(-1 * var(--float-tilt, 1deg))) scale(1, 1);
      animation-timing-function: cubic-bezier(0.33, 0.66, 0.66, 1);
    }
    90% {
      transform: translateY(calc(0.05 * var(--float-height, 6px))) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
      animation-timing-function: cubic-bezier(0.33, 0, 0.66, 1);
    }
    100% {
      transform: translateY(0) translateX(0) rotate(0deg)
        scale(var(--float-squash-x, 1.02), var(--float-squash-y, 0.98));
    }
  }

  @keyframes swing {
    0% {
      transform: rotate(0deg);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    8% {
      transform: rotate(var(--swing-angle, 22deg));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    18% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.85));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    28% {
      transform: rotate(calc(var(--swing-angle, 22deg) * 0.65));
      animation-timing-function: cubic-bezier(0.35, 0, 0.65, 1);
    }
    38% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.45));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    48% {
      transform: rotate(calc(var(--swing-angle, 22deg) * 0.25));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    56% {
      transform: rotate(calc(-1 * var(--swing-angle, 22deg) * 0.1));
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    64% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(0deg);
    }
  }

  @keyframes jello {
    0% {
      transform: scale(1, 1);
      animation-timing-function: cubic-bezier(0.2, 0, 0.8, 1);
    }
    12% {
      transform: scale(var(--jello-scale-x, 1.15), calc(2 - var(--jello-scale-x, 1.15)));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    24% {
      transform: scale(calc(2 - var(--jello-scale-y, 1.12)), var(--jello-scale-y, 1.12));
      animation-timing-function: cubic-bezier(0.3, 0, 0.7, 1);
    }
    36% {
      transform: scale(
        calc(1 + (var(--jello-scale-x, 1.15) - 1) * 0.5),
        calc(2 - (1 + (var(--jello-scale-x, 1.15) - 1) * 0.5))
      );
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    48% {
      transform: scale(
        calc(2 - (1 + (var(--jello-scale-y, 1.12) - 1) * 0.3)),
        calc(1 + (var(--jello-scale-y, 1.12) - 1) * 0.3)
      );
      animation-timing-function: cubic-bezier(0.4, 0, 0.6, 1);
    }
    58% {
      transform: scale(1.02, 0.98);
      animation-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
    }
    68% {
      transform: scale(1, 1);
    }
    100% {
      transform: scale(1, 1);
    }
  }

  /* #endregion */
`;var icons={check:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M434.8 70.1c14.3 10.4 17.5 30.4 7.1 44.7l-256 352c-5.5 7.6-14 12.3-23.4 13.1s-18.5-2.7-25.1-9.3l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l101.5 101.5 234-321.7c10.4-14.3 30.4-17.5 44.7-7.1z"/></svg>',"chevron-down":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M201.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 338.7 54.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z"/></svg>',"chevron-left":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M9.4 233.4c-12.5 12.5-12.5 32.8 0 45.3l192 192c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256 246.6 86.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-192 192z"/></svg>',"chevron-right":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M311.1 233.4c12.5 12.5 12.5 32.8 0 45.3l-192 192c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L243.2 256 73.9 86.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l192 192z"/></svg>',"circle-check":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill-rule="evenodd" d="M256 0a256 256 0 1 0 0 512a256 256 0 1 0 0-512zM144 264l32-32 56 56 112-112 32 32-144 144z"/></svg>',gear:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M259.1 73.5C262.1 58.7 275.2 48 290.4 48L350.2 48C365.4 48 378.5 58.7 381.5 73.5L396 143.5C410.1 149.5 423.3 157.2 435.3 166.3L503.1 143.8C517.5 139 533.3 145 540.9 158.2L570.8 210C578.4 223.2 575.7 239.8 564.3 249.9L511 297.3C511.9 304.7 512.3 312.3 512.3 320C512.3 327.7 511.8 335.3 511 342.7L564.4 390.2C575.8 400.3 578.4 417 570.9 430.1L541 481.9C533.4 495 517.6 501.1 503.2 496.3L435.4 473.8C423.3 482.9 410.1 490.5 396.1 496.6L381.7 566.5C378.6 581.4 365.5 592 350.4 592L290.6 592C275.4 592 262.3 581.3 259.3 566.5L244.9 496.6C230.8 490.6 217.7 482.9 205.6 473.8L137.5 496.3C123.1 501.1 107.3 495.1 99.7 481.9L69.8 430.1C62.2 416.9 64.9 400.3 76.3 390.2L129.7 342.7C128.8 335.3 128.4 327.7 128.4 320C128.4 312.3 128.9 304.7 129.7 297.3L76.3 249.8C64.9 239.7 62.3 223 69.8 209.9L99.7 158.1C107.3 144.9 123.1 138.9 137.5 143.7L205.3 166.2C217.4 157.1 230.6 149.5 244.6 143.4L259.1 73.5zM320.3 400C364.5 399.8 400.2 363.9 400 319.7C399.8 275.5 363.9 239.8 319.7 240C275.5 240.2 239.8 276.1 240 320.3C240.2 364.5 276.1 400.2 320.3 400z"/></svg>',info:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill-rule="evenodd" d="M256 0a256 256 0 1 0 0 512a256 256 0 1 0 0-512zM256 112a32 32 0 1 0 0 64a32 32 0 1 0 0-64zM208 224h72v128h32v32h-112v-32h32v-96h-24z"/></svg>',"magnifying-glass":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z"/></svg>',minus:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M0 256c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32z"/></svg>',plus:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 128C352 110.3 337.7 96 320 96C302.3 96 288 110.3 288 128L288 288L128 288C110.3 288 96 302.3 96 320C96 337.7 110.3 352 128 352L288 352L288 512C288 529.7 302.3 544 320 544C337.7 544 352 529.7 352 512L352 352L512 352C529.7 352 544 337.7 544 320C544 302.3 529.7 288 512 288L352 288L352 128z"/></svg>',star:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M309.5-18.9c-4.1-8-12.4-13.1-21.4-13.1s-17.3 5.1-21.4 13.1L193.1 125.3 33.2 150.7c-8.9 1.4-16.3 7.7-19.1 16.3s-.5 18 5.8 24.4l114.4 114.5-25.2 159.9c-1.4 8.9 2.3 17.9 9.6 23.2s16.9 6.1 25 2L288.1 417.6 432.4 491c8 4.1 17.7 3.3 25-2s11-14.2 9.6-23.2L441.7 305.9 556.1 191.4c6.4-6.4 8.6-15.8 5.8-24.4s-10.1-14.9-19.1-16.3L383 125.3 309.5-18.9z"/></svg>',user:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M224 248a120 120 0 1 0 0-240 120 120 0 1 0 0 240zm-29.7 56C95.8 304 16 383.8 16 482.3 16 498.7 29.3 512 45.7 512l356.6 0c16.4 0 29.7-13.3 29.7-29.7 0-98.5-79.8-178.3-178.3-178.3l-59.4 0z"/></svg>',warning:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill-rule="evenodd" d="M256 32L496 464H16zM232 176h48v160h-48zM256 364a28 28 0 1 0 0 56a28 28 0 1 0 0-56z"/></svg>',xmark:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M55.1 73.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L147.2 256 9.9 393.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L192.5 301.3 329.9 438.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L237.8 256 375.1 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L192.5 210.7 55.1 73.4z"/></svg>',"circle-info":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill-rule="evenodd" d="M256 0a256 256 0 1 0 0 512a256 256 0 1 0 0-512zM256 112a32 32 0 1 0 0 64a32 32 0 1 0 0-64zM208 224h72v128h32v32h-112v-32h32v-96h-24z"/></svg>',"triangle-exclamation":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill-rule="evenodd" d="M256 32L496 464H16zM232 176h48v160h-48zM256 364a28 28 0 1 0 0 56a28 28 0 1 0 0-56z"/></svg>'},offlineLibrary={name:"default",resolver:name=>"data:image/svg+xml,"+encodeURIComponent(icons[name]??""),mutator:svg=>{svg.hasAttribute("fill")||svg.setAttribute("fill","currentColor")}};var library_default_default=offlineLibrary;function dataUri(svg){return`data:image/svg+xml,${encodeURIComponent(svg)}`}var icons2={solid:{"arrow-down":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M169.4 502.6c12.5 12.5 32.8 12.5 45.3 0l160-160c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 402.7 224 32c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 370.7-105.4-105.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160z"/></svg>',"arrow-up":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M214.6 9.4c-12.5-12.5-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L160 109.3 160 480c0 17.7 14.3 32 32 32s32-14.3 32-32l0-370.7 105.4 105.4c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-160-160z"/></svg>',backward:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M236.3 107.1C247.9 96 265 92.9 279.7 99.2C294.4 105.5 304 120 304 136L304 272.3L476.3 107.2C487.9 96 505 92.9 519.7 99.2C534.4 105.5 544 120 544 136L544 504C544 520 534.4 534.5 519.7 540.8C505 547.1 487.9 544 476.3 532.9L304 367.7L304 504C304 520 294.4 534.5 279.7 540.8C265 547.1 247.9 544 236.3 532.9L44.3 348.9C36.5 341.3 32 330.9 32 320C32 309.1 36.5 298.7 44.3 291.1L236.3 107.1z"/></svg>',"backward-step":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M491 100.8C478.1 93.8 462.3 94.5 450 102.6L192 272.1L192 128C192 110.3 177.7 96 160 96C142.3 96 128 110.3 128 128L128 512C128 529.7 142.3 544 160 544C177.7 544 192 529.7 192 512L192 367.9L450 537.5C462.3 545.6 478 546.3 491 539.3C504 532.3 512 518.8 512 504.1L512 136.1C512 121.4 503.9 107.9 491 100.9z"/></svg>',bars:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.3.1 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free (Icons: CC BY 4.0, Fonts: SIL OFL 1.1, Code: MIT License) Copyright 2026 Fonticons, Inc. --><path d="M0 96C0 78.3 14.3 64 32 64l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 128C14.3 128 0 113.7 0 96zM0 256c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32zM448 416c0 17.7-14.3 32-32 32L32 448c-17.7 0-32-14.3-32-32s14.3-32 32-32l384 0c17.7 0 32 14.3 32 32z"/></svg>',"angles-left":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M77.3 256 214.7 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256zm192 0L406.7 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-160 160c-12.5 12.5-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L269.3 256z"/></svg>',"angles-right":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M434.7 256 297.3 118.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l160 160c12.5 12.5 12.5 32.8 0 45.3l-160 160c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L434.7 256zm-192 0L105.3 118.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l160 160c12.5 12.5 12.5 32.8 0 45.3l-160 160c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L242.7 256z"/></svg>',check:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M434.8 70.1c14.3 10.4 17.5 30.4 7.1 44.7l-256 352c-5.5 7.6-14 12.3-23.4 13.1s-18.5-2.7-25.1-9.3l-128-128c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l101.5 101.5 234-321.7c10.4-14.3 30.4-17.5 44.7-7.1z"/></svg>',"chevron-down":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M201.4 406.6c12.5 12.5 32.8 12.5 45.3 0l192-192c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L224 338.7 54.6 169.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l192 192z"/></svg>',"chevron-left":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M9.4 233.4c-12.5 12.5-12.5 32.8 0 45.3l192 192c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L77.3 256 246.6 86.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0l-192 192z"/></svg>',"chevron-right":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M311.1 233.4c12.5 12.5 12.5 32.8 0 45.3l-192 192c-12.5 12.5-32.8 12.5-45.3 0s-12.5-32.8 0-45.3L243.2 256 73.9 86.6c-12.5-12.5-12.5-32.8 0-45.3s32.8-12.5 45.3 0l192 192z"/></svg>',circle:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0z"/></svg>',"closed-captioning":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M64 192C64 156.7 92.7 128 128 128L512 128C547.3 128 576 156.7 576 192L576 448C576 483.3 547.3 512 512 512L128 512C92.7 512 64 483.3 64 448L64 192zM216 272L248 272C252.4 272 256 275.6 256 280C256 293.3 266.7 304 280 304C293.3 304 304 293.3 304 280C304 249.1 278.9 224 248 224L216 224C185.1 224 160 249.1 160 280L160 360C160 390.9 185.1 416 216 416L248 416C278.9 416 304 390.9 304 360C304 346.7 293.3 336 280 336C266.7 336 256 346.7 256 360C256 364.4 252.4 368 248 368L216 368C211.6 368 208 364.4 208 360L208 280C208 275.6 211.6 272 216 272zM384 280C384 275.6 387.6 272 392 272L424 272C428.4 272 432 275.6 432 280C432 293.3 442.7 304 456 304C469.3 304 480 293.3 480 280C480 249.1 454.9 224 424 224L392 224C361.1 224 336 249.1 336 280L336 360C336 390.9 361.1 416 392 416L424 416C454.9 416 480 390.9 480 360C480 346.7 469.3 336 456 336C442.7 336 432 346.7 432 360C432 364.4 428.4 368 424 368L392 368C387.6 368 384 364.4 384 360L384 280z"/></svg>',"closed-captioning-slash":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M39 39.1C48.4 29.7 63.6 29.7 72.9 39.1L161.8 128L512 128C547.3 128 576 156.7 576 192L576 448C576 473.5 561.1 495.4 539.6 505.8L601 567.1C610.4 576.5 610.4 591.7 601 601C591.6 610.3 576.4 610.4 567.1 601L39 73.1C29.7 63.7 29.7 48.5 39 39.1zM384 350.1L384 279.9C384 275.5 387.6 271.9 392 271.9L424 271.9C428.4 271.9 432 275.5 432 279.9C432 293.2 442.7 303.9 456 303.9C469.3 303.9 480 293.2 480 279.9C480 249 454.9 223.9 424 223.9L392 223.9C361.1 223.9 336 249 336 279.9L336 302.1L384 350.1zM445.5 411.6C465.7 403.2 480 383.2 480 359.9C480 346.6 469.3 335.9 456 335.9C442.7 335.9 432 346.6 432 359.9C432 364.3 428.4 367.9 424 367.9L401.8 367.9L445.5 411.6zM162.3 264.1C160.8 269.1 160 274.5 160 280L160 360C160 390.9 185.1 416 216 416L248 416C266.1 416 282.1 407.5 292.4 394.2L410.2 512L128 512C92.7 512 64 483.3 64 448L64 192C64 184.2 65.4 176.7 68 169.8L162.3 264.1zM256.1 357.9C256 358.6 256 359.3 256 360C256 364.4 252.4 368 248 368L216 368C211.6 368 208 364.4 208 360L208 309.8L256.1 357.9z"/></svg>',compress:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M160 64c0-17.7-14.3-32-32-32S96 46.3 96 64l0 64-64 0c-17.7 0-32 14.3-32 32s14.3 32 32 32l96 0c17.7 0 32-14.3 32-32l0-96zM32 320c-17.7 0-32 14.3-32 32s14.3 32 32 32l64 0 0 64c0 17.7 14.3 32 32 32s32-14.3 32-32l0-96c0-17.7-14.3-32-32-32l-96 0zM352 64c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 96c0 17.7 14.3 32 32 32l96 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-64 0 0-64zM320 320c-17.7 0-32 14.3-32 32l0 96c0 17.7 14.3 32 32 32s32-14.3 32-32l0-64 64 0c17.7 0 32-14.3 32-32s-14.3-32-32-32l-96 0z"/></svg>',ellipsis:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.3.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M96 320C96 289.1 121.1 264 152 264C182.9 264 208 289.1 208 320C208 350.9 182.9 376 152 376C121.1 376 96 350.9 96 320zM264 320C264 289.1 289.1 264 320 264C350.9 264 376 289.1 376 320C376 350.9 350.9 376 320 376C289.1 376 264 350.9 264 320zM488 264C518.9 264 544 289.1 544 320C544 350.9 518.9 376 488 376C457.1 376 432 350.9 432 320C432 289.1 457.1 264 488 264z"/></svg>',"ellipsis-vertical":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M320 208C289.1 208 264 182.9 264 152C264 121.1 289.1 96 320 96C350.9 96 376 121.1 376 152C376 182.9 350.9 208 320 208zM320 432C350.9 432 376 457.1 376 488C376 518.9 350.9 544 320 544C289.1 544 264 518.9 264 488C264 457.1 289.1 432 320 432zM376 320C376 350.9 350.9 376 320 376C289.1 376 264 350.9 264 320C264 289.1 289.1 264 320 264C350.9 264 376 289.1 376 320z"/></svg>',expand:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 96C110.3 96 96 110.3 96 128L96 224C96 241.7 110.3 256 128 256C145.7 256 160 241.7 160 224L160 160L224 160C241.7 160 256 145.7 256 128C256 110.3 241.7 96 224 96L128 96zM160 416C160 398.3 145.7 384 128 384C110.3 384 96 398.3 96 416L96 512C96 529.7 110.3 544 128 544L224 544C241.7 544 256 529.7 256 512C256 494.3 241.7 480 224 480L160 480L160 416zM416 96C398.3 96 384 110.3 384 128C384 145.7 398.3 160 416 160L480 160L480 224C480 241.7 494.3 256 512 256C529.7 256 544 241.7 544 224L544 128C544 110.3 529.7 96 512 96L416 96zM544 416C544 398.3 529.7 384 512 384C494.3 384 480 398.3 480 416L480 480L416 480C398.3 480 384 494.3 384 512C384 529.7 398.3 544 416 544L512 544C529.7 544 544 529.7 544 512L544 416z"/></svg>',eyedropper:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M341.6 29.2l-101.6 101.6-9.4-9.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3l160 160c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3l-9.4-9.4 101.6-101.6c39-39 39-102.2 0-141.1s-102.2-39-141.1 0zM55.4 323.3c-15 15-23.4 35.4-23.4 56.6l0 42.4-26.6 39.9c-8.5 12.7-6.8 29.6 4 40.4s27.7 12.5 40.4 4l39.9-26.6 42.4 0c21.2 0 41.6-8.4 56.6-23.4l109.4-109.4-45.3-45.3-109.4 109.4c-3 3-7.1 4.7-11.3 4.7l-36.1 0 0-36.1c0-4.2 1.7-8.3 4.7-11.3l109.4-109.4-45.3-45.3-109.4 109.4z"/></svg>',filter:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 64C19.1 64 7.4 71.8 2.4 83.8S.2 109.5 9.4 118.6L192 301.3 192 416c0 8.5 3.4 16.6 9.4 22.6l64 64c9.2 9.2 22.9 11.9 34.9 6.9S320 492.9 320 480l0-178.7 182.6-182.6c9.2-9.2 11.9-22.9 6.9-34.9S492.9 64 480 64L32 64z"/></svg>',forward:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M403.7 107.1C392.1 96 375 92.9 360.3 99.2C345.6 105.5 336 120 336 136L336 272.3L163.7 107.2C152.1 96 135 92.9 120.3 99.2C105.6 105.5 96 120 96 136L96 504C96 520 105.6 534.5 120.3 540.8C135 547.1 152.1 544 163.7 532.9L336 367.7L336 504C336 520 345.6 534.5 360.3 540.8C375 547.1 392.1 544 403.7 532.9L595.7 348.9C603.6 341.4 608 330.9 608 320C608 309.1 603.5 298.7 595.7 291.1L403.7 107.1z"/></svg>',file:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M192 64C156.7 64 128 92.7 128 128L128 512C128 547.3 156.7 576 192 576L448 576C483.3 576 512 547.3 512 512L512 234.5C512 217.5 505.3 201.2 493.3 189.2L386.7 82.7C374.7 70.7 358.5 64 341.5 64L192 64zM453.5 240L360 240C346.7 240 336 229.3 336 216L336 122.5L453.5 240z"/></svg>',"file-audio":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM389.8 307.7C380.7 301.4 368.3 303.6 362 312.7C355.7 321.8 357.9 334.2 367 340.5C390.9 357.2 406.4 384.8 406.4 416C406.4 447.2 390.8 474.9 367 491.5C357.9 497.8 355.7 510.3 362 519.3C368.3 528.3 380.8 530.6 389.8 524.3C423.9 500.5 446.4 460.8 446.4 416C446.4 371.2 424 331.5 389.8 307.7zM208 376C199.2 376 192 383.2 192 392L192 440C192 448.8 199.2 456 208 456L232 456L259.2 490C262.2 493.8 266.8 496 271.7 496L272 496C280.8 496 288 488.8 288 480L288 352C288 343.2 280.8 336 272 336L271.7 336C266.8 336 262.2 338.2 259.2 342L232 376L208 376zM336 448.2C336 458.9 346.5 466.4 354.9 459.8C367.8 449.5 376 433.7 376 416C376 398.3 367.8 382.5 354.9 372.2C346.5 365.5 336 373.1 336 383.8L336 448.3z"/></svg>',"file-code":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM282.2 359.6C290.8 349.5 289.7 334.4 279.6 325.8C269.5 317.2 254.4 318.3 245.8 328.4L197.8 384.4C190.1 393.4 190.1 406.6 197.8 415.6L245.8 471.6C254.4 481.7 269.6 482.8 279.6 474.2C289.6 465.6 290.8 450.4 282.2 440.4L247.6 400L282.2 359.6zM394.2 328.4C385.6 318.3 370.4 317.2 360.4 325.8C350.4 334.4 349.2 349.6 357.8 359.6L392.4 400L357.8 440.4C349.2 450.5 350.3 465.6 360.4 474.2C370.5 482.8 385.6 481.7 394.2 471.6L442.2 415.6C449.9 406.6 449.9 393.4 442.2 384.4L394.2 328.4z"/></svg>',"file-excel":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM292 330.7C284.6 319.7 269.7 316.7 258.7 324C247.7 331.3 244.7 346.3 252 357.3L291.2 416L252 474.7C244.6 485.7 247.6 500.6 258.7 508C269.8 515.4 284.6 512.4 292 501.3L320 459.3L348 501.3C355.4 512.3 370.3 515.3 381.3 508C392.3 500.7 395.3 485.7 388 474.7L348.8 416L388 357.3C395.4 346.3 392.4 331.4 381.3 324C370.2 316.6 355.4 319.6 348 330.7L320 372.7L292 330.7z"/></svg>',"file-image":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM256 320C256 302.3 241.7 288 224 288C206.3 288 192 302.3 192 320C192 337.7 206.3 352 224 352C241.7 352 256 337.7 256 320zM220.6 512L419.4 512C435.2 512 448 499.2 448 483.4C448 476.1 445.2 469 440.1 463.7L343.3 361.9C337.3 355.6 328.9 352 320.1 352L319.8 352C311 352 302.7 355.6 296.6 361.9L199.9 463.7C194.8 469 192 476.1 192 483.4C192 499.2 204.8 512 220.6 512z"/></svg>',"file-pdf":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 64C92.7 64 64 92.7 64 128L64 512C64 547.3 92.7 576 128 576L208 576L208 464C208 428.7 236.7 400 272 400L448 400L448 234.5C448 217.5 441.3 201.2 429.3 189.2L322.7 82.7C310.7 70.7 294.5 64 277.5 64L128 64zM389.5 240L296 240C282.7 240 272 229.3 272 216L272 122.5L389.5 240zM272 444C261 444 252 453 252 464L252 592C252 603 261 612 272 612C283 612 292 603 292 592L292 564L304 564C337.1 564 364 537.1 364 504C364 470.9 337.1 444 304 444L272 444zM304 524L292 524L292 484L304 484C315 484 324 493 324 504C324 515 315 524 304 524zM400 444C389 444 380 453 380 464L380 592C380 603 389 612 400 612L432 612C460.7 612 484 588.7 484 560L484 496C484 467.3 460.7 444 432 444L400 444zM420 572L420 484L432 484C438.6 484 444 489.4 444 496L444 560C444 566.6 438.6 572 432 572L420 572zM508 464L508 592C508 603 517 612 528 612C539 612 548 603 548 592L548 548L576 548C587 548 596 539 596 528C596 517 587 508 576 508L548 508L548 484L576 484C587 484 596 475 596 464C596 453 587 444 576 444L528 444C517 444 508 453 508 464z"/></svg>',"file-powerpoint":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM280 320C266.7 320 256 330.7 256 344L256 488C256 501.3 266.7 512 280 512C293.3 512 304 501.3 304 488L304 464L328 464C367.8 464 400 431.8 400 392C400 352.2 367.8 320 328 320L280 320zM328 416L304 416L304 368L328 368C341.3 368 352 378.7 352 392C352 405.3 341.3 416 328 416z"/></svg>',"file-video":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM208 368L208 464C208 481.7 222.3 496 240 496L336 496C353.7 496 368 481.7 368 464L368 440L403 475C406.2 478.2 410.5 480 415 480C424.4 480 432 472.4 432 463L432 368.9C432 359.5 424.4 351.9 415 351.9C410.5 351.9 406.2 353.7 403 356.9L368 391.9L368 367.9C368 350.2 353.7 335.9 336 335.9L240 335.9C222.3 335.9 208 350.2 208 367.9z"/></svg>',"file-word":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM263.4 338.8C260.5 325.9 247.7 317.7 234.8 320.6C221.9 323.5 213.7 336.3 216.6 349.2L248.6 493.2C250.9 503.7 260 511.4 270.8 512C281.6 512.6 291.4 505.9 294.8 495.6L320 419.9L345.2 495.6C348.6 505.8 358.4 512.5 369.2 512C380 511.5 389.1 503.8 391.4 493.2L423.4 349.2C426.3 336.3 418.1 323.4 405.2 320.6C392.3 317.8 379.4 325.9 376.6 338.8L363.4 398.2L342.8 336.4C339.5 326.6 330.4 320 320 320C309.6 320 300.5 326.6 297.2 336.4L276.6 398.2L263.4 338.8z"/></svg>',"file-zipper":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M128 128C128 92.7 156.7 64 192 64L341.5 64C358.5 64 374.8 70.7 386.8 82.7L493.3 189.3C505.3 201.3 512 217.6 512 234.6L512 512C512 547.3 483.3 576 448 576L192 576C156.7 576 128 547.3 128 512L128 128zM336 122.5L336 216C336 229.3 346.7 240 360 240L453.5 240L336 122.5zM192 136C192 149.3 202.7 160 216 160L264 160C277.3 160 288 149.3 288 136C288 122.7 277.3 112 264 112L216 112C202.7 112 192 122.7 192 136zM192 232C192 245.3 202.7 256 216 256L264 256C277.3 256 288 245.3 288 232C288 218.7 277.3 208 264 208L216 208C202.7 208 192 218.7 192 232zM256 304L224 304C206.3 304 192 318.3 192 336L192 384C192 410.5 213.5 432 240 432C266.5 432 288 410.5 288 384L288 336C288 318.3 273.7 304 256 304zM240 368C248.8 368 256 375.2 256 384C256 392.8 248.8 400 240 400C231.2 400 224 392.8 224 384C224 375.2 231.2 368 240 368z"/></svg>',"forward-step":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M21 36.8c12.9-7 28.7-6.3 41 1.8L320 208.1 320 64c0-17.7 14.3-32 32-32s32 14.3 32 32l0 384c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-144.1-258 169.6c-12.3 8.1-28 8.8-41 1.8S0 454.7 0 440L0 72C0 57.3 8.1 43.8 21 36.8z"/></svg>',gauge:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zm320 96c0-26.9-16.5-49.9-40-59.3L280 120c0-13.3-10.7-24-24-24s-24 10.7-24 24l0 172.7c-23.5 9.5-40 32.5-40 59.3 0 35.3 28.7 64 64 64s64-28.7 64-64zM144 176a32 32 0 1 0 0-64 32 32 0 1 0 0 64zm-16 80a32 32 0 1 0 -64 0 32 32 0 1 0 64 0zm288 32a32 32 0 1 0 0-64 32 32 0 1 0 0 64zM400 144a32 32 0 1 0 -64 0 32 32 0 1 0 64 0z"/></svg>',gear:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M259.1 73.5C262.1 58.7 275.2 48 290.4 48L350.2 48C365.4 48 378.5 58.7 381.5 73.5L396 143.5C410.1 149.5 423.3 157.2 435.3 166.3L503.1 143.8C517.5 139 533.3 145 540.9 158.2L570.8 210C578.4 223.2 575.7 239.8 564.3 249.9L511 297.3C511.9 304.7 512.3 312.3 512.3 320C512.3 327.7 511.8 335.3 511 342.7L564.4 390.2C575.8 400.3 578.4 417 570.9 430.1L541 481.9C533.4 495 517.6 501.1 503.2 496.3L435.4 473.8C423.3 482.9 410.1 490.5 396.1 496.6L381.7 566.5C378.6 581.4 365.5 592 350.4 592L290.6 592C275.4 592 262.3 581.3 259.3 566.5L244.9 496.6C230.8 490.6 217.7 482.9 205.6 473.8L137.5 496.3C123.1 501.1 107.3 495.1 99.7 481.9L69.8 430.1C62.2 416.9 64.9 400.3 76.3 390.2L129.7 342.7C128.8 335.3 128.4 327.7 128.4 320C128.4 312.3 128.9 304.7 129.7 297.3L76.3 249.8C64.9 239.7 62.3 223 69.8 209.9L99.7 158.1C107.3 144.9 123.1 138.9 137.5 143.7L205.3 166.2C217.4 157.1 230.6 149.5 244.6 143.4L259.1 73.5zM320.3 400C364.5 399.8 400.2 363.9 400 319.7C399.8 275.5 363.9 239.8 319.7 240C275.5 240.2 239.8 276.1 240 320.3C240.2 364.5 276.1 400.2 320.3 400z"/></svg>',"grip-vertical":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M128 40c0-22.1-17.9-40-40-40L40 0C17.9 0 0 17.9 0 40L0 88c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zm0 192c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM0 424l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 40c0-22.1-17.9-40-40-40L232 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48zM192 232l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40zM320 424c0-22.1-17.9-40-40-40l-48 0c-22.1 0-40 17.9-40 40l0 48c0 22.1 17.9 40 40 40l48 0c22.1 0 40-17.9 40-40l0-48z"/></svg>',indeterminate:'<svg part="indeterminate-icon" class="icon" viewBox="0 0 16 16"><g stroke="none" stroke-width="1" fill="none" fill-rule="evenodd" stroke-linecap="round"><g stroke="currentColor" stroke-width="2"><g transform="translate(2.285714 6.857143)"><path d="M10.2857143,1.14285714 L1.14285714,1.14285714"/></g></g></g></svg>',"magnifying-glass":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M416 208c0 45.9-14.9 88.3-40 122.7L502.6 457.4c12.5 12.5 12.5 32.8 0 45.3s-32.8 12.5-45.3 0L330.7 376C296.3 401.1 253.9 416 208 416 93.1 416 0 322.9 0 208S93.1 0 208 0 416 93.1 416 208zM208 352a144 144 0 1 0 0-288 144 144 0 1 0 0 288z"/></svg>',minus:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M0 256c0-17.7 14.3-32 32-32l384 0c17.7 0 32 14.3 32 32s-14.3 32-32 32L32 288c-17.7 0-32-14.3-32-32z"/></svg>',pause:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M48 32C21.5 32 0 53.5 0 80L0 432c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48L48 32zm224 0c-26.5 0-48 21.5-48 48l0 352c0 26.5 21.5 48 48 48l64 0c26.5 0 48-21.5 48-48l0-352c0-26.5-21.5-48-48-48l-64 0z"/></svg>',"picture-in-picture":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M448 32c35.3 0 64 28.7 64 64l0 112-64 0 0-112-384 0 0 320 144 0 0 64-144 0-6.5-.3c-30.1-3.1-54.1-27-57.1-57.1L0 416 0 96C0 62.9 25.2 35.6 57.5 32.3L64 32 448 32zm16 224c26.5 0 48 21.5 48 48l0 128c0 26.5-21.5 48-48 48l-160 0c-26.5 0-48-21.5-48-48l0-128c0-26.5 21.5-48 48-48l160 0z"/></svg>',play:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M91.2 36.9c-12.4-6.8-27.4-6.5-39.6 .7S32 57.9 32 72l0 368c0 14.1 7.5 27.2 19.6 34.4s27.2 7.5 39.6 .7l336-184c12.8-7 20.8-20.5 20.8-35.1s-8-28.1-20.8-35.1l-336-184z"/></svg>',"play-circle":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zM188.3 147.1c-7.6 4.2-12.3 12.3-12.3 20.9l0 176c0 8.7 4.7 16.7 12.3 20.9s16.8 4.1 24.3-.5l144-88c7.1-4.4 11.5-12.1 11.5-20.5s-4.4-16.1-11.5-20.5l-144-88c-7.4-4.5-16.7-4.7-24.3-.5z"/></svg>',plus:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 128C352 110.3 337.7 96 320 96C302.3 96 288 110.3 288 128L288 288L128 288C110.3 288 96 302.3 96 320C96 337.7 110.3 352 128 352L288 352L288 512C288 529.7 302.3 544 320 544C337.7 544 352 529.7 352 512L352 352L512 352C529.7 352 544 337.7 544 320C544 302.3 529.7 288 512 288L352 288L352 128z"/></svg>',star:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M309.5-18.9c-4.1-8-12.4-13.1-21.4-13.1s-17.3 5.1-21.4 13.1L193.1 125.3 33.2 150.7c-8.9 1.4-16.3 7.7-19.1 16.3s-.5 18 5.8 24.4l114.4 114.5-25.2 159.9c-1.4 8.9 2.3 17.9 9.6 23.2s16.9 6.1 25 2L288.1 417.6 432.4 491c8 4.1 17.7 3.3 25-2s11-14.2 9.6-23.2L441.7 305.9 556.1 191.4c6.4-6.4 8.6-15.8 5.8-24.4s-10.1-14.9-19.1-16.3L383 125.3 309.5-18.9z"/></svg>',"table-columns":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M0 96C0 60.7 28.7 32 64 32l320 0c35.3 0 64 28.7 64 64l0 320c0 35.3-28.7 64-64 64L64 480c-35.3 0-64-28.7-64-64L0 96zm64 64l0 256 128 0 0-256-128 0zm320 0l-128 0 0 256 128 0 0-256z"/></svg>',thumbtack:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M32 32C32 14.3 46.3 0 64 0L320 0c17.7 0 32 14.3 32 32s-14.3 32-32 32l-29.5 0 10.3 134.1c37.1 21.2 65.8 56.4 78.2 99.7l3.8 13.4c2.8 9.7 .8 20-5.2 28.1S362 352 352 352L32 352c-10 0-19.5-4.7-25.5-12.7s-8-18.4-5.2-28.1L5 297.8c12.4-43.3 41-78.5 78.2-99.7L93.5 64 64 64C46.3 64 32 49.7 32 32zM160 400l64 0 0 112c0 17.7-14.3 32-32 32s-32-14.3-32-32l0-112z"/></svg>',"up-down":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M406.6 502.6l96-96c9.2-9.2 11.9-22.9 6.9-34.9S492.9 352 480 352l-64 0 0-320c0-17.7-14.3-32-32-32s-32 14.3-32 32l0 320-64 0c-12.9 0-24.6 7.8-29.6 19.8s-2.2 25.7 6.9 34.9l96 96c12.5 12.5 32.8 12.5 45.3 0zM150.6 9.4c-12.5-12.5-32.8-12.5-45.3 0l-96 96c-9.2 9.2-11.9 22.9-6.9 34.9S19.1 160 32 160l64 0 0 320c0 17.7 14.3 32 32 32s32-14.3 32-32l0-320 64 0c12.9 0 24.6-7.8 29.6-19.8s2.2-25.7-6.9-34.9l-96-96z"/></svg>',upload:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free 7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M352 173.3L352 384C352 401.7 337.7 416 320 416C302.3 416 288 401.7 288 384L288 173.3L246.6 214.7C234.1 227.2 213.8 227.2 201.3 214.7C188.8 202.2 188.8 181.9 201.3 169.4L297.3 73.4C309.8 60.9 330.1 60.9 342.6 73.4L438.6 169.4C451.1 181.9 451.1 202.2 438.6 214.7C426.1 227.2 405.8 227.2 393.3 214.7L352 173.3zM320 464C364.2 464 400 428.2 400 384L480 384C515.3 384 544 412.7 544 448L544 480C544 515.3 515.3 544 480 544L160 544C124.7 544 96 515.3 96 480L96 448C96 412.7 124.7 384 160 384L240 384C240 428.2 275.8 464 320 464zM464 488C477.3 488 488 477.3 488 464C488 450.7 477.3 440 464 440C450.7 440 440 450.7 440 464C440 477.3 450.7 488 464 488z"/></svg>',user:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M224 248a120 120 0 1 0 0-240 120 120 0 1 0 0 240zm-29.7 56C95.8 304 16 383.8 16 482.3 16 498.7 29.3 512 45.7 512l356.6 0c16.4 0 29.7-13.3 29.7-29.7 0-98.5-79.8-178.3-178.3-178.3l-59.4 0z"/></svg>',volume:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM441.1 107c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C443.3 170.7 464 210.9 464 256s-20.7 85.3-53.2 111.8c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5c43.2-35.2 70.9-88.9 70.9-149s-27.7-113.8-70.9-149zm-60.5 74.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C361.1 227.6 368 241 368 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C402.1 312.9 416 286.1 416 256s-13.9-56.9-35.5-74.5z"/></svg>',"volume-low":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM380.6 181.5c-10.3-8.4-25.4-6.8-33.8 3.5s-6.8 25.4 3.5 33.8C361.1 227.6 368 241 368 256s-6.9 28.4-17.7 37.3c-10.3 8.4-11.8 23.5-3.5 33.8s23.5 11.8 33.8 3.5C402.1 312.9 416 286.1 416 256s-13.9-56.9-35.5-74.5z"/></svg>',"volume-xmark":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M48 352l48 0 134.1 119.2c6.4 5.7 14.6 8.8 23.1 8.8 19.2 0 34.8-15.6 34.8-34.8l0-378.4c0-19.2-15.6-34.8-34.8-34.8-8.5 0-16.7 3.1-23.1 8.8L96 160 48 160c-26.5 0-48 21.5-48 48l0 96c0 26.5 21.5 48 48 48zM367 175c-9.4 9.4-9.4 24.6 0 33.9l47 47-47 47c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l47-47 47 47c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-47-47 47-47c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-47 47-47-47c-9.4-9.4-24.6-9.4-33.9 0z"/></svg>',xmark:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 384 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M55.1 73.4c-12.5-12.5-32.8-12.5-45.3 0s-12.5 32.8 0 45.3L147.2 256 9.9 393.4c-12.5 12.5-12.5 32.8 0 45.3s32.8 12.5 45.3 0L192.5 301.3 329.9 438.6c12.5 12.5 32.8 12.5 45.3 0s12.5-32.8 0-45.3L237.8 256 375.1 118.6c12.5-12.5 12.5-32.8 0-45.3s-32.8-12.5-45.3 0L192.5 210.7 55.1 73.4z"/></svg>'},regular:{calendar:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M216 64C229.3 64 240 74.7 240 88L240 128L400 128L400 88C400 74.7 410.7 64 424 64C437.3 64 448 74.7 448 88L448 128L480 128C515.3 128 544 156.7 544 192L544 480C544 515.3 515.3 544 480 544L160 544C124.7 544 96 515.3 96 480L96 192C96 156.7 124.7 128 160 128L192 128L192 88C192 74.7 202.7 64 216 64zM216 176L160 176C151.2 176 144 183.2 144 192L144 240L496 240L496 192C496 183.2 488.8 176 480 176L216 176zM144 288L144 480C144 488.8 151.2 496 160 496L480 496C488.8 496 496 488.8 496 480L496 288L144 288z"/></svg>',"circle-question":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M464 256a208 208 0 1 0 -416 0 208 208 0 1 0 416 0zM0 256a256 256 0 1 1 512 0 256 256 0 1 1 -512 0zm256-80c-17.7 0-32 14.3-32 32 0 13.3-10.7 24-24 24s-24-10.7-24-24c0-44.2 35.8-80 80-80s80 35.8 80 80c0 47.2-36 67.2-56 74.5l0 3.8c0 13.3-10.7 24-24 24s-24-10.7-24-24l0-8.1c0-20.5 14.8-35.2 30.1-40.2 6.4-2.1 13.2-5.5 18.2-10.3 4.3-4.2 7.7-10 7.7-19.6 0-17.7-14.3-32-32-32zM224 368a32 32 0 1 1 64 0 32 32 0 1 1 -64 0z"/></svg>',"circle-xmark":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M256 48a208 208 0 1 1 0 416 208 208 0 1 1 0-416zm0 464a256 256 0 1 0 0-512 256 256 0 1 0 0 512zM167 167c-9.4 9.4-9.4 24.6 0 33.9l55 55-55 55c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l55-55 55 55c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-55-55 55-55c9.4-9.4 9.4-24.6 0-33.9s-24.6-9.4-33.9 0l-55 55-55-55c-9.4-9.4-24.6-9.4-33.9 0z"/></svg>',clock:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"><!--!Font Awesome Free v7.2.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2026 Fonticons, Inc.--><path d="M528 320C528 434.9 434.9 528 320 528C205.1 528 112 434.9 112 320C112 205.1 205.1 112 320 112C434.9 112 528 205.1 528 320zM64 320C64 461.4 178.6 576 320 576C461.4 576 576 461.4 576 320C576 178.6 461.4 64 320 64C178.6 64 64 178.6 64 320zM296 184L296 320C296 328 300 335.5 306.7 340L402.7 404C413.7 411.4 428.6 408.4 436 397.3C443.4 386.2 440.4 371.4 429.3 364L344 307.2L344 184C344 170.7 333.3 160 320 160C306.7 160 296 170.7 296 184z"/></svg>',copy:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 448 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M384 336l-192 0c-8.8 0-16-7.2-16-16l0-256c0-8.8 7.2-16 16-16l133.5 0c4.2 0 8.3 1.7 11.3 4.7l58.5 58.5c3 3 4.7 7.1 4.7 11.3L400 320c0 8.8-7.2 16-16 16zM192 384l192 0c35.3 0 64-28.7 64-64l0-197.5c0-17-6.7-33.3-18.7-45.3L370.7 18.7C358.7 6.7 342.5 0 325.5 0L192 0c-35.3 0-64 28.7-64 64l0 256c0 35.3 28.7 64 64 64zM64 128c-35.3 0-64 28.7-64 64L0 448c0 35.3 28.7 64 64 64l192 0c35.3 0 64-28.7 64-64l0-16-48 0 0 16c0 8.8-7.2 16-16 16L64 464c-8.8 0-16-7.2-16-16l0-256c0-8.8 7.2-16 16-16l16 0 0-48-16 0z"/></svg>',eye:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M288 80C222.8 80 169.2 109.6 128.1 147.7 89.6 183.5 63 226 49.4 256 63 286 89.6 328.5 128.1 364.3 169.2 402.4 222.8 432 288 432s118.8-29.6 159.9-67.7C486.4 328.5 513 286 526.6 256 513 226 486.4 183.5 447.9 147.7 406.8 109.6 353.2 80 288 80zM95.4 112.6C142.5 68.8 207.2 32 288 32s145.5 36.8 192.6 80.6c46.8 43.5 78.1 95.4 93 131.1 3.3 7.9 3.3 16.7 0 24.6-14.9 35.7-46.2 87.7-93 131.1-47.1 43.7-111.8 80.6-192.6 80.6S142.5 443.2 95.4 399.4c-46.8-43.5-78.1-95.4-93-131.1-3.3-7.9-3.3-16.7 0-24.6 14.9-35.7 46.2-87.7 93-131.1zM288 336c44.2 0 80-35.8 80-80 0-29.6-16.1-55.5-40-69.3-1.4 59.7-49.6 107.9-109.3 109.3 13.8 23.9 39.7 40 69.3 40zm-79.6-88.4c2.5 .3 5 .4 7.6 .4 35.3 0 64-28.7 64-64 0-2.6-.2-5.1-.4-7.6-37.4 3.9-67.2 33.7-71.1 71.1zm45.6-115c10.8-3 22.2-4.5 33.9-4.5 8.8 0 17.5 .9 25.8 2.6 .3 .1 .5 .1 .8 .2 57.9 12.2 101.4 63.7 101.4 125.2 0 70.7-57.3 128-128 128-61.6 0-113-43.5-125.2-101.4-1.8-8.6-2.8-17.5-2.8-26.6 0-11 1.4-21.8 4-32 .2-.7 .3-1.3 .5-1.9 11.9-43.4 46.1-77.6 89.5-89.5z"/></svg>',"eye-slash":'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M41-24.9c-9.4-9.4-24.6-9.4-33.9 0S-2.3-.3 7 9.1l528 528c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-96.4-96.4c2.7-2.4 5.4-4.8 8-7.2 46.8-43.5 78.1-95.4 93-131.1 3.3-7.9 3.3-16.7 0-24.6-14.9-35.7-46.2-87.7-93-131.1-47.1-43.7-111.8-80.6-192.6-80.6-56.8 0-105.6 18.2-146 44.2L41-24.9zM176.9 111.1c32.1-18.9 69.2-31.1 111.1-31.1 65.2 0 118.8 29.6 159.9 67.7 38.5 35.7 65.1 78.3 78.6 108.3-13.6 30-40.2 72.5-78.6 108.3-3.1 2.8-6.2 5.6-9.4 8.4L393.8 328c14-20.5 22.2-45.3 22.2-72 0-70.7-57.3-128-128-128-26.7 0-51.5 8.2-72 22.2l-39.1-39.1zm182 182l-108-108c11.1-5.8 23.7-9.1 37.1-9.1 44.2 0 80 35.8 80 80 0 13.4-3.3 26-9.1 37.1zM103.4 173.2l-34-34c-32.6 36.8-55 75.8-66.9 104.5-3.3 7.9-3.3 16.7 0 24.6 14.9 35.7 46.2 87.7 93 131.1 47.1 43.7 111.8 80.6 192.6 80.6 37.3 0 71.2-7.9 101.5-20.6L352.2 422c-20 6.4-41.4 10-64.2 10-65.2 0-118.8-29.6-159.9-67.7-38.5-35.7-65.1-78.3-78.6-108.3 10.4-23.1 28.6-53.6 54-82.8z"/></svg>',star:'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 576 512"><!--! Font Awesome Free 7.0.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc. --><path d="M288.1-32c9 0 17.3 5.1 21.4 13.1L383 125.3 542.9 150.7c8.9 1.4 16.3 7.7 19.1 16.3s.5 18-5.8 24.4L441.7 305.9 467 465.8c1.4 8.9-2.3 17.9-9.6 23.2s-17 6.1-25 2L288.1 417.6 143.8 491c-8 4.1-17.7 3.3-25-2s-11-14.2-9.6-23.2L134.4 305.9 20 191.4c-6.4-6.4-8.6-15.8-5.8-24.4s10.1-14.9 19.1-16.3l159.9-25.4 73.6-144.2c4.1-8 12.4-13.1 21.4-13.1zm0 76.8L230.3 158c-3.5 6.8-10 11.6-17.6 12.8l-125.5 20 89.8 89.9c5.4 5.4 7.9 13.1 6.7 20.7l-19.8 125.5 113.3-57.6c6.8-3.5 14.9-3.5 21.8 0l113.3 57.6-19.8-125.5c-1.2-7.6 1.3-15.3 6.7-20.7l89.8-89.9-125.5-20c-7.6-1.2-14.1-6-17.6-12.8L288.1 44.8z"/></svg>'}},systemLibrary={name:"system",resolver:(name,_family="classic",variant="solid")=>{let svg=icons2[variant][name]??icons2.regular[name]??icons2.regular["circle-question"];return svg?dataUri(svg):""},mutator:svg=>{svg.hasAttribute("fill")||svg.setAttribute("fill","currentColor")}},library_system_default=systemLibrary;var defaultIconFamily="classic",registry=[library_default_default,library_system_default],watchedIcons=new Set;function watchIcon(icon){watchedIcons.add(icon)}function unwatchIcon(icon){watchedIcons.delete(icon)}function getIconLibrary(name){return registry.find(lib=>lib.name===name)}function registerIconLibrary(name,options){unregisterIconLibrary(name),registry.push({name,resolver:options.resolver,mutator:options.mutator,spriteSheet:options.spriteSheet}),watchedIcons.forEach(icon=>{icon.library===name&&icon.setIcon()})}function unregisterIconLibrary(name){registry=registry.filter(lib=>lib.name!==name)}function getDefaultIconFamily(){return defaultIconFamily}var{I:t5}=j;var l4=(o10,t6)=>t6===void 0?o10?._$litType$!==void 0:o10?._$litType$===t6;var r6=o10=>o10.strings===void 0;var m2={},p3=(o10,t6=m2)=>o10._$AH=t6;var CACHEABLE_ERROR=Symbol(),RETRYABLE_ERROR=Symbol(),parser,iconCache=new Map,WaIcon=class extends WebAwesomeElement{constructor(){super(...arguments),this.svg=null,this.autoWidth=!1,this.swapOpacity=!1,this.label="",this.library="default",this.rotate=0,this.resolveIcon=async(url,library)=>{let fileData;if(library?.spriteSheet){this.hasUpdated||await this.updateComplete,this.svg=b2`<svg part="svg">
        <use part="use" href="${url}"></use>
      </svg>`,await this.updateComplete;let svg=this.shadowRoot.querySelector("[part='svg']");return typeof library.mutator=="function"&&library.mutator(svg,this),this.svg}try{if(fileData=await fetch(url,{mode:"cors"}),!fileData.ok)return fileData.status===410?CACHEABLE_ERROR:RETRYABLE_ERROR}catch{return RETRYABLE_ERROR}try{let div=document.createElement("div");div.innerHTML=await fileData.text();let svg=div.firstElementChild;if(svg?.tagName?.toLowerCase()!=="svg")return CACHEABLE_ERROR;parser||(parser=new DOMParser);let svgEl=parser.parseFromString(svg.outerHTML,"text/html").body.querySelector("svg");return svgEl?(svgEl.part.add("svg"),document.adoptNode(svgEl)):CACHEABLE_ERROR}catch{return CACHEABLE_ERROR}}}connectedCallback(){super.connectedCallback(),watchIcon(this)}firstUpdated(changedProperties){super.firstUpdated(changedProperties),this.hasAttribute("rotate")&&this.style.setProperty("--rotate-angle",`${this.rotate}deg`),this.setIcon()}disconnectedCallback(){super.disconnectedCallback(),unwatchIcon(this)}async getIconSource(){let library=getIconLibrary(this.library),family=this.family||getDefaultIconFamily();if(this.name&&library){let autoWidth=this.canvas==="auto"||this.autoWidth,url;try{url=await library.resolver(this.name,family,this.variant,autoWidth)}catch{url=void 0}return{url,fromLibrary:!0}}return{url:this.src,fromLibrary:!1}}handleLabelChange(){typeof this.label=="string"&&this.label.length>0?(this.setAttribute("role","img"),this.setAttribute("aria-label",this.label),this.removeAttribute("aria-hidden")):(this.removeAttribute("role"),this.removeAttribute("aria-label"),this.setAttribute("aria-hidden","true"))}async setIcon(){let{url,fromLibrary}=await this.getIconSource(),library=fromLibrary?getIconLibrary(this.library):void 0;if(!url){this.svg=null;return}let iconResolver=iconCache.get(url);iconResolver||(iconResolver=this.resolveIcon(url,library),iconCache.set(url,iconResolver));let svg=await iconResolver;svg===RETRYABLE_ERROR&&iconCache.delete(url);let sourceAfterFetch=await this.getIconSource();if(url===sourceAfterFetch.url){if(l4(svg)){this.svg=svg;return}switch(svg){case RETRYABLE_ERROR:case CACHEABLE_ERROR:this.svg=null,this.dispatchEvent(new WaErrorEvent);break;default:this.svg=svg.cloneNode(!0),library?.mutator?.(this.svg,this),this.dispatchEvent(new WaLoadEvent)}}}willUpdate(changedProperties){return this.style||this.setStyleProperty("--rotate-angle",`${this.rotate}deg`),super.willUpdate(changedProperties)}updated(changedProperties){super.updated(changedProperties);let library=getIconLibrary(this.library);this.hasAttribute("rotate")&&this.style.setProperty("--rotate-angle",`${this.rotate}deg`);let svg=this.shadowRoot?.querySelector("svg");svg&&library?.mutator?.(svg,this)}render(){return this.hasUpdated?this.svg:b2`<svg part="svg" width="16" height="16" viewBox="0 0 16 16"></svg>`}};WaIcon.css=icon_styles_default;__decorateClass([r5()],WaIcon.prototype,"svg",2);__decorateClass([n4({reflect:!0})],WaIcon.prototype,"name",2);__decorateClass([n4({reflect:!0})],WaIcon.prototype,"family",2);__decorateClass([n4({reflect:!0})],WaIcon.prototype,"variant",2);__decorateClass([n4({reflect:!0})],WaIcon.prototype,"canvas",2);__decorateClass([n4({attribute:"auto-width",type:Boolean,reflect:!0})],WaIcon.prototype,"autoWidth",2);__decorateClass([n4({attribute:"swap-opacity",type:Boolean,reflect:!0})],WaIcon.prototype,"swapOpacity",2);__decorateClass([n4()],WaIcon.prototype,"src",2);__decorateClass([n4()],WaIcon.prototype,"label",2);__decorateClass([n4({reflect:!0})],WaIcon.prototype,"library",2);__decorateClass([n4({type:Number,reflect:!0})],WaIcon.prototype,"rotate",2);__decorateClass([n4({type:String,reflect:!0})],WaIcon.prototype,"flip",2);__decorateClass([n4({type:String,reflect:!0})],WaIcon.prototype,"animation",2);__decorateClass([watch("label")],WaIcon.prototype,"handleLabelChange",1);__decorateClass([watch(["family","name","library","variant","src","autoWidth","canvas","swapOpacity"],{waitUntilFirstUpdate:!0})],WaIcon.prototype,"setIcon",1);WaIcon=__decorateClass([t3("wa-icon")],WaIcon);var button_group_styles_default=i`
  :host {
    display: inline-flex;
  }

  .button-group {
    display: flex;
    position: relative;
    isolation: isolate;
    flex-wrap: wrap;

    @media (hover: hover) {
      > :hover,
      &::slotted(:hover) {
        z-index: 1;
      }
    }

    /* Focus and checked are always on top */
    > :focus,
    &::slotted(:focus),
    > [aria-checked='true'],
    &::slotted([aria-checked='true']),
    > [checked],
    &::slotted([checked]) {
      z-index: 2 !important;
    }

    :host([orientation='horizontal']) & {
      flex-direction: row;
    }

    :host([orientation='vertical']) & {
      flex-direction: column;
    }
  }

  /* Set custom properties to be inherited by slotted buttons */
  :host([orientation='horizontal']) {
    --_button-horizontal-indent: var(--wa-form-control-border-width);
    --_button-horizontal-indent-outlined: calc(var(--wa-form-control-border-width) * -1);

    ::slotted(:first-child) {
      --_button-horizontal-indent: 0;
      --_button-horizontal-indent-outlined: 0;
    }
  }

  :host([orientation='vertical']) {
    --_button-vertical-indent: var(--wa-form-control-border-width);
    --_button-vertical-indent-outlined: calc(var(--wa-form-control-border-width) * -1);

    ::slotted(:first-child) {
      --_button-vertical-indent: 0;
      --_button-vertical-indent-outlined: 0;
    }
  }

  /* All buttons that are not in front or at the end get their border radius removed */
  ::slotted(:not(:first-child):not(:last-child)) {
    --_button-start-start-radius: 0;
    --_button-start-end-radius: 0;
    --_button-end-start-radius: 0;
    --_button-end-end-radius: 0;
  }

  /* Remove leading and trailing buttons border radius individually */
  :host([orientation='horizontal']) {
    ::slotted(:first-child:not(:last-child)) {
      --_button-start-end-radius: 0;
      --_button-end-end-radius: 0;
    }

    ::slotted(:last-child:not(:first-child)) {
      --_button-start-start-radius: 0;
      --_button-end-start-radius: 0;
    }
  }

  :host([orientation='vertical']) {
    ::slotted(:first-child:not(:last-child)) {
      --_button-end-start-radius: 0;
      --_button-end-end-radius: 0;
    }

    ::slotted(:last-child:not(:first-child)) {
      --_button-start-start-radius: 0;
      --_button-start-end-radius: 0;
    }
  }
`;var WaButtonGroup=class extends WebAwesomeElement{constructor(){super(...arguments),this.disableRole=!1,this.hasOutlined=!1,this.label="",this.orientation="horizontal"}updated(changedProperties){super.updated(changedProperties),changedProperties.has("orientation")&&this.setAttribute("aria-orientation",this.orientation)}handleFocus(event){findButton(event.target)?.classList.add("button-focus")}handleBlur(event){findButton(event.target)?.classList.remove("button-focus")}handleMouseOver(event){findButton(event.target)?.classList.add("button-hover")}handleMouseOut(event){findButton(event.target)?.classList.remove("button-hover")}render(){return b2`
      <slot
        part="base"
        class="button-group"
        role="${this.disableRole?"presentation":"group"}"
        aria-label=${this.label}
        aria-orientation=${this.orientation}
        @focusout=${this.handleBlur}
        @focusin=${this.handleFocus}
        @mouseover=${this.handleMouseOver}
        @mouseout=${this.handleMouseOut}
      ></slot>
    `}};WaButtonGroup.css=[button_group_styles_default];__decorateClass([e5("slot")],WaButtonGroup.prototype,"defaultSlot",2);__decorateClass([r5()],WaButtonGroup.prototype,"disableRole",2);__decorateClass([r5()],WaButtonGroup.prototype,"hasOutlined",2);__decorateClass([n4()],WaButtonGroup.prototype,"label",2);__decorateClass([n4({reflect:!0})],WaButtonGroup.prototype,"orientation",2);WaButtonGroup=__decorateClass([t3("wa-button-group")],WaButtonGroup);function findButton(el){let selector="wa-button, wa-radio-button";return el.closest(selector)??el.querySelector(selector)}var callout_styles_default=i`
  :host {
    display: flex;
    position: relative;
    align-items: stretch;
    border-radius: var(--wa-panel-border-radius);
    background-color: var(--wa-color-fill-quiet, var(--wa-color-brand-fill-quiet));
    border-color: var(--wa-color-border-quiet, var(--wa-color-brand-border-quiet));
    border-style: var(--wa-panel-border-style);
    border-width: var(--wa-panel-border-width);
    color: var(--wa-color-text-normal);
    padding: 1em;
  }

  /* Appearance modifiers */
  :host([appearance~='plain']) {
    background-color: transparent;
    border-color: transparent;
  }

  :host([appearance~='outlined']) {
    background-color: transparent;
    border-color: var(--wa-color-border-loud, var(--wa-color-brand-border-loud));
  }

  :host([appearance~='filled']) {
    background-color: var(--wa-color-fill-quiet, var(--wa-color-brand-fill-quiet));
    border-color: transparent;
  }

  :host([appearance~='filled-outlined']) {
    border-color: var(--wa-color-border-quiet, var(--wa-color-brand-border-quiet));
  }

  :host([appearance~='accent']) {
    color: var(--wa-color-on-loud, var(--wa-color-brand-on-loud));
    background-color: var(--wa-color-fill-loud, var(--wa-color-brand-fill-loud));
    border-color: transparent;

    [part~='icon'] {
      color: currentColor;
    }
  }

  [part~='icon'] {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-on-quiet);
    font-size: 1.25em;
  }

  ::slotted([slot='icon']) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  [part~='message'] {
    flex: 1 1 auto;
    display: block;
    overflow: hidden;
  }
`;var WaCallout=class extends WebAwesomeElement{constructor(){super(...arguments),this.variant="brand",this.size="m"}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}render(){return b2`
      <div part="icon">
        <slot name="icon"></slot>
      </div>

      <div part="message">
        <slot></slot>
      </div>
    `}};WaCallout.css=[callout_styles_default,variants_styles_default,size_styles_default];__decorateClass([n4({reflect:!0})],WaCallout.prototype,"variant",2);__decorateClass([n4({reflect:!0})],WaCallout.prototype,"appearance",2);__decorateClass([n4({reflect:!0})],WaCallout.prototype,"size",2);__decorateClass([watch("size")],WaCallout.prototype,"handleSizeChange",1);WaCallout=__decorateClass([t3("wa-callout")],WaCallout);var card_styles_default=i`
  :host {
    --spacing: var(--wa-space-l);

    /* Internal calculated properties */
    --inner-border-radius: calc(var(--wa-panel-border-radius) - var(--wa-panel-border-width));

    display: flex;
    flex-direction: column;
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
    border-radius: var(--wa-panel-border-radius);
    border-style: var(--wa-panel-border-style);
    box-shadow: var(--wa-shadow-s);
    border-width: var(--wa-panel-border-width);
    color: var(--wa-color-text-normal);
  }

  /* Appearance modifiers */
  :host([appearance='plain']) {
    background-color: transparent;
    border-color: transparent;
    box-shadow: none;
  }

  :host([appearance='outlined']) {
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='filled']) {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: transparent;
  }

  :host([appearance='filled-outlined']) {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='accent']) {
    color: var(--wa-color-neutral-on-loud);
    background-color: var(--wa-color-neutral-fill-loud);
    border-color: transparent;
  }

  /* Take care of top and bottom radii */
  .media,
  :host(:not([with-media])) .header,
  :host(:not([with-media], [with-header])) .body {
    border-start-start-radius: var(--inner-border-radius);
    border-start-end-radius: var(--inner-border-radius);
  }

  :host(:not([with-footer])) .body,
  .footer {
    border-end-start-radius: var(--inner-border-radius);
    border-end-end-radius: var(--inner-border-radius);
  }

  .media {
    display: flex;
    overflow: hidden;

    &::slotted(*) {
      display: block;
      width: 100%;
      border-radius: 0 !important;
    }
  }

  /* Round all corners for plain appearance */
  :host([appearance='plain']) .media {
    border-radius: var(--inner-border-radius);

    &::slotted(*) {
      border-radius: inherit !important;
    }
  }

  .header {
    display: block;
    border-block-end-style: inherit;
    border-block-end-color: var(--wa-color-surface-border);
    border-block-end-width: var(--wa-panel-border-width);
    padding: calc(var(--spacing) / 2) var(--spacing);
  }

  .body {
    display: block;
    padding: var(--spacing);
  }

  .footer {
    display: block;
    border-block-start-style: inherit;
    border-block-start-color: var(--wa-color-surface-border);
    border-block-start-width: var(--wa-panel-border-width);
    padding: var(--spacing);
  }

  /* Push slots to sides when the action slots renders */
  .has-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  :host(:not([with-header])) .header,
  :host(:not([with-footer])) .footer,
  :host(:not([with-media])) .media {
    display: none;
  }

  /* Orientation Styles */
  :host([orientation='horizontal']) {
    flex-direction: row;

    .media {
      border-start-start-radius: var(--inner-border-radius);
      border-end-start-radius: var(--inner-border-radius);
      border-start-end-radius: 0;

      &::slotted(*) {
        block-size: 100%;
        inline-size: 100%;
        object-fit: cover;
      }
    }
  }

  :host([orientation='horizontal']) .body slot::slotted(*) {
    display: block;
    height: 100%;
    margin: 0;
  }

  :host([orientation='horizontal']) slot[name='actions']::slotted(*) {
    display: flex;
    align-items: center;
    padding: var(--spacing);
  }
`;var WaCard=class extends WebAwesomeElement{constructor(){super(...arguments),this.hasSlotController=new HasSlotController(this,"footer","header","media","header-actions","footer-actions","actions"),this.appearance="outlined",this.withHeader=!1,this.withMedia=!1,this.withFooter=!1,this.withHeaderActions=!1,this.withFooterActions=!1,this.orientation="vertical"}willUpdate(changedProperties){this.withHeader=this.hasSlotController.test("header","withHeader"),this.withMedia=this.hasSlotController.test("media","withMedia"),this.withFooter=this.hasSlotController.test("footer","withFooter"),super.willUpdate(changedProperties)}render(){if(this.orientation==="horizontal")return b2`
        <slot name="media" part="media" class="media"></slot>
        <div part="body" class="body"><slot></slot></div>
        <slot name="actions" part="actions" class="actions"></slot>
      `;let hasHeaderActions=this.hasSlotController.test("header-actions","withHeaderActions"),hasFooterActions=this.hasSlotController.test("footer-actions","withFooterActions");return b2`
      <slot name="media" part="media" class="media"></slot>

      <div
        part="header"
        class=${e7({header:!0,"has-actions":hasHeaderActions})}
      >
        <slot name="header"></slot>
        <slot name="header-actions"></slot>
      </div>

      <div part="body" class="body"><slot></slot></div>

      <div
        part="footer"
        class=${e7({footer:!0,"has-actions":hasFooterActions})}
      >
        <slot name="footer"></slot>
        <slot name="footer-actions"></slot>
      </div>
    `}};WaCard.css=[size_styles_default,card_styles_default];__decorateClass([n4({reflect:!0})],WaCard.prototype,"appearance",2);__decorateClass([n4({attribute:"with-header",type:Boolean,reflect:!0})],WaCard.prototype,"withHeader",2);__decorateClass([n4({attribute:"with-media",type:Boolean,reflect:!0})],WaCard.prototype,"withMedia",2);__decorateClass([n4({attribute:"with-footer",type:Boolean,reflect:!0})],WaCard.prototype,"withFooter",2);__decorateClass([n4({attribute:"with-header-actions",type:Boolean,reflect:!0})],WaCard.prototype,"withHeaderActions",2);__decorateClass([n4({attribute:"with-footer-actions",type:Boolean,reflect:!0})],WaCard.prototype,"withFooterActions",2);__decorateClass([n4({reflect:!0})],WaCard.prototype,"orientation",2);WaCard=__decorateClass([t3("wa-card")],WaCard);WaCard.disableWarning?.("change-in-update");var checkbox_styles_default=i`
  :host {
    --checked-icon-color: var(--wa-color-brand-on-loud);
    --checked-icon-scale: 0.8;

    display: inline-flex;
    color: var(--wa-form-control-value-color);
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    user-select: none;
    -webkit-user-select: none;
  }

  [part~='control'] {
    display: inline-flex;
    flex: 0 0 auto;
    position: relative;
    align-items: center;
    justify-content: center;
    width: var(--wa-form-control-toggle-size);
    height: var(--wa-form-control-toggle-size);
    border-color: var(--wa-form-control-border-color);
    border-radius: min(
      calc(var(--wa-form-control-toggle-size) * 0.375),
      var(--wa-border-radius-s)
    ); /* min prevents entirely circular checkbox */
    border-style: var(--wa-border-style);
    border-width: var(--wa-form-control-border-width);
    background-color: var(--wa-form-control-background-color);
    transition:
      background var(--wa-transition-normal),
      border-color var(--wa-transition-fast),
      box-shadow var(--wa-transition-fast),
      color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);

    margin-inline-end: 0.5em;
  }

  [part~='base'] {
    display: flex;
    align-items: flex-start;
    position: relative;
    color: currentColor;
    vertical-align: middle;
    cursor: pointer;
  }

  [part~='label'] {
    display: inline;
  }

  /* Checked */
  [part~='control']:has(:checked, :indeterminate) {
    color: var(--checked-icon-color);
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-form-control-activated-color);
  }

  /* Focus */
  [part~='control']:has(> input:focus-visible:not(:disabled)) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled */
  :host [part~='base']:has(input:disabled) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  input {
    position: absolute;
    padding: 0;
    margin: 0;
    height: 100%;
    width: 100%;
    opacity: 0;
    pointer-events: none;
  }

  [part~='icon'] {
    display: flex;
    scale: var(--checked-icon-scale);

    /* Without this, Safari renders the icon slightly to the left */
    &::part(svg) {
      translate: 0.0009765625em;
    }

    input:not(:checked, :indeterminate) + & {
      visibility: hidden;
    }
  }

  :host([required]) [part~='label']::after {
    content: var(--wa-form-control-required-content);
    color: var(--wa-form-control-required-content-color);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }
`;var RequiredValidator=(options={})=>{let{validationElement,validationProperty}=options;validationElement||typeof document<"u"&&"createElement"in document&&(validationElement=Object.assign(document.createElement("input"),{required:!0})),validationProperty||(validationProperty="value");let obj={observedAttributes:["required"],message:validationElement?.validationMessage,checkValidity(element){let validity={message:"",isValid:!0,invalidKeys:[]};return(element.required??element.hasAttribute("required"))&&!element[validationProperty]&&(validity.message=typeof obj.message=="function"?obj.message(element):obj.message||"",validity.isValid=!1,validity.invalidKeys.push("valueMissing")),validity}};return obj};var form_control_styles_default=i`
  :host {
    display: flex;
    flex-direction: column;
  }

  /* Treat wrapped labels, inputs, and hints as direct children of the host element */
  [part~='form-control'] {
    display: contents;
  }

  /* Label */
  :is([part~='form-control-label'], [part~='label']):has(*:not(:empty)),
  :is([part~='form-control-label'], [part~='label']).has-label {
    display: inline-flex;
    color: var(--wa-form-control-label-color);
    font-weight: var(--wa-form-control-label-font-weight);
    line-height: var(--wa-form-control-label-line-height);
    margin-block-end: 0.5em;
  }

  :host([required]) :is([part~='form-control-label'], [part~='label'])::after {
    content: var(--wa-form-control-required-content);
    margin-inline-start: var(--wa-form-control-required-content-offset);
    color: var(--wa-form-control-required-content-color);
  }

  /* Help text */
  [part~='hint'] {
    display: block;
    color: var(--wa-form-control-hint-color);
    font-weight: var(--wa-form-control-hint-font-weight);
    line-height: var(--wa-form-control-hint-line-height);
    margin-block-start: 0.5em;
    font-size: var(--wa-font-size-smaller);

    &:not(.has-slotted, .has-hint, .has-count) {
      display: none;
    }
  }
`;var l5=e6(class extends i5{constructor(r8){if(super(r8),r8.type!==t4.PROPERTY&&r8.type!==t4.ATTRIBUTE&&r8.type!==t4.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!r6(r8))throw Error("`live` bindings can only contain a single expression")}render(r8){return r8}update(i8,[t6]){if(t6===E||t6===A)return t6;let o10=i8.element,l6=i8.name;if(i8.type===t4.PROPERTY){if(t6===o10[l6])return E}else if(i8.type===t4.BOOLEAN_ATTRIBUTE){if(!!t6===o10.hasAttribute(l6))return E}else if(i8.type===t4.ATTRIBUTE&&o10.getAttribute(l6)===t6+"")return E;return p3(i8),t6}});var WaCheckbox=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.hasSlotController=new HasSlotController(this,"hint"),this.title="",this._value=this.getAttribute("value")??null,this.size="m",this.disabled=!1,this.indeterminate=!1,this._checked=null,this.defaultChecked=this.hasAttribute("checked"),this.required=!1,this.hint=""}static get validators(){let validators=[RequiredValidator({validationProperty:"checked",validationElement:Object.assign(document.createElement("input"),{type:"checkbox",required:!0})})];return[...super.validators,...validators]}get value(){return this._value??"on"}set value(val){this._value=val}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}get checked(){return this.valueHasChanged?!!this._checked:this._checked??this.defaultChecked}set checked(val){this._checked=!!val,this.valueHasChanged=!0}handleClick(){this.hasInteracted=!0,this.checked=!this.checked,this.indeterminate=!1,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}connectedCallback(){if(super.connectedCallback(),this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleDefaultCheckedChange()});return}this.handleDefaultCheckedChange()}handleDefaultCheckedChange(){this.handleValueOrCheckedChange()}handleValueOrCheckedChange(){if(this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleValueOrCheckedChange()});return}this.setValue(this.checked?this.value:null,this._value),this.updateValidity()}handleStateChange(){this.hasUpdated&&(this.input.checked=this.checked,this.input.indeterminate=this.indeterminate),this.customStates.set("checked",this.checked),this.customStates.set("indeterminate",this.indeterminate),this.updateValidity()}handleDisabledChange(){this.customStates.set("disabled",this.disabled)}willUpdate(changedProperties){super.willUpdate(changedProperties),(changedProperties.has("value")||changedProperties.has("checked")||changedProperties.has("defaultChecked")||changedProperties.has("disabled"))&&this.handleValueOrCheckedChange()}formResetCallback(){this._checked=null,super.formResetCallback(),this.handleValueOrCheckedChange()}click(){this.input.click()}focus(options){this.input.focus(options)}blur(){this.input.blur()}render(){let hasHintSlot=this.hasSlotController.test("hint"),hasHint=this.hint?!0:!!hasHintSlot,isIndeterminate=!this.checked&&this.indeterminate,iconName=isIndeterminate?"indeterminate":"check",iconState=isIndeterminate?"indeterminate":"checked",checkedAttribute=this.didSSR&&!this.hasUpdated?this.checked:this.defaultChecked,checkedProperty=this.didSSR&&!this.hasUpdated?null:l5(this.checked);return b2`
      <label part="base checkbox">
        <span part="control">
          <input
            class="input"
            type="checkbox"
            title=${this.title}
            name=${o7(this.name)}
            value=${o7(this.value)}
            .indeterminate=${l5(this.indeterminate)}
            .checked=${o7(checkedProperty)}
            ?checked=${checkedAttribute}
            ?disabled=${this.disabled}
            ?required=${this.required}
            aria-checked=${this.indeterminate?"mixed":this.checked?"true":"false"}
            aria-describedby="hint"
            @click=${this.handleClick}
          />

          <wa-icon part="${iconState}-icon icon" library="system" name=${iconName}></wa-icon>
        </span>

        <slot part="label"></slot>
      </label>

      <slot
        id="hint"
        part="hint"
        name="hint"
        aria-hidden=${hasHint?"false":"true"}
        class="${e7({"has-slotted":hasHint})}"
      >
        ${this.hint}
      </slot>
    `}};WaCheckbox.css=[form_control_styles_default,size_styles_default,checkbox_styles_default];WaCheckbox.shadowRootOptions={...WebAwesomeFormAssociatedElement.shadowRootOptions,delegatesFocus:!0};__decorateClass([e5('input[type="checkbox"]')],WaCheckbox.prototype,"input",2);__decorateClass([n4()],WaCheckbox.prototype,"title",2);__decorateClass([n4({reflect:!0})],WaCheckbox.prototype,"value",1);__decorateClass([n4({reflect:!0})],WaCheckbox.prototype,"size",2);__decorateClass([watch("size")],WaCheckbox.prototype,"handleSizeChange",1);__decorateClass([n4({type:Boolean})],WaCheckbox.prototype,"disabled",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaCheckbox.prototype,"indeterminate",2);__decorateClass([n4({type:Boolean,attribute:!1})],WaCheckbox.prototype,"checked",1);__decorateClass([n4({type:Boolean,reflect:!0,attribute:"checked"})],WaCheckbox.prototype,"defaultChecked",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaCheckbox.prototype,"required",2);__decorateClass([n4()],WaCheckbox.prototype,"hint",2);__decorateClass([watch(["checked","defaultChecked"])],WaCheckbox.prototype,"handleDefaultCheckedChange",1);__decorateClass([watch(["checked","indeterminate"])],WaCheckbox.prototype,"handleStateChange",1);__decorateClass([watch("disabled")],WaCheckbox.prototype,"handleDisabledChange",1);WaCheckbox=__decorateClass([t3("wa-checkbox")],WaCheckbox);WaCheckbox.disableWarning?.("change-in-update");var details_styles_default=i`
  :host {
    --spacing: var(--wa-space-m);
    --show-duration: var(--wa-transition-normal);
    --hide-duration: var(--wa-transition-normal);

    display: block;
  }

  details {
    display: block;
    overflow-anchor: none;
    border: var(--wa-panel-border-width) var(--wa-color-surface-border) var(--wa-panel-border-style);
    background-color: var(--wa-color-surface-default);
    border-radius: var(--wa-panel-border-radius);
    color: var(--wa-color-text-normal);

    /* Print styles */
    @media print {
      background: none;
      border: solid var(--wa-border-width-s) var(--wa-color-surface-border);

      summary {
        list-style: none;
      }
    }
  }

  /* Appearance modifiers */
  :host([appearance='plain']) details {
    background-color: transparent;
    border-color: transparent;
    border-radius: 0;
  }

  :host([appearance='outlined']) details {
    background-color: var(--wa-color-surface-default);
    border-color: var(--wa-color-surface-border);
  }

  :host([appearance='filled']) details {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: transparent;
  }

  :host([appearance='filled-outlined']) details {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-border-quiet);
  }

  :host([disabled]) details {
    opacity: 0.5;
    cursor: not-allowed;
  }

  summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--spacing);
    padding: var(--spacing); /* Add padding here */
    border-radius: calc(var(--wa-panel-border-radius) - var(--wa-panel-border-width));
    user-select: none;
    -webkit-user-select: none;
    cursor: pointer;

    &::marker,
    &::-webkit-details-marker {
      display: none;
    }

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: calc(var(--wa-panel-border-width) + var(--wa-focus-ring-offset));
    }
  }

  :host([open]) summary {
    border-end-start-radius: 0;
    border-end-end-radius: 0;
  }

  /* 'Start' icon placement */
  :host([icon-placement='start']) summary {
    flex-direction: row-reverse;
    justify-content: start;
  }

  [part~='icon'] {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-text-quiet);
    transition: rotate var(--wa-transition-normal) var(--wa-transition-easing);
  }

  :host([open]) [part~='icon'] {
    rotate: 90deg;
  }

  :host([open]:dir(rtl)) [part~='icon'] {
    rotate: -90deg;
  }

  :host([open]) slot[name='expand-icon'],
  :host(:not([open])) slot[name='collapse-icon'] {
    display: none;
  }

  .body.animating {
    overflow: hidden;
  }

  .content {
    display: block;
    box-sizing: border-box; /* Ensure contents don't overflow */
    padding-block-start: var(--spacing);
    padding-inline: var(--spacing); /* Add horizontal padding */
    padding-block-end: var(--spacing); /* Add bottom padding */
  }
`;var WaShowEvent=class extends Event{constructor(){super("wa-show",{bubbles:!0,cancelable:!0,composed:!0})}};var WaHideEvent=class extends Event{constructor(detail){super("wa-hide",{bubbles:!0,cancelable:!0,composed:!0}),this.detail=detail}};var WaAfterHideEvent=class extends Event{constructor(){super("wa-after-hide",{bubbles:!0,cancelable:!1,composed:!0})}};var WaAfterShowEvent=class extends Event{constructor(){super("wa-after-show",{bubbles:!0,cancelable:!1,composed:!0})}};function waitForEvent(el,eventName){return new Promise(resolve=>{function done(event){event.target===el&&(el.removeEventListener(eventName,done),resolve())}el.addEventListener(eventName,done)})}async function animate(el,keyframes,options){return el.animate(keyframes,options).finished.catch(()=>{})}function animateWithClass(el,className){return new Promise(resolve=>{let controller=new AbortController,{signal}=controller;if(el.classList.contains(className))return;el.classList.add(className);let resolved=!1,onEnd=()=>{resolved||(resolved=!0,el.classList.remove(className),resolve(),controller.abort())};el.addEventListener("animationend",onEnd,{once:!0,signal}),el.addEventListener("animationcancel",onEnd,{once:!0,signal}),requestAnimationFrame(()=>{!resolved&&el.getAnimations().length===0&&onEnd()})})}function parseDuration(duration){return duration=duration.toString().toLowerCase(),duration.indexOf("ms")>-1?parseFloat(duration)||0:duration.indexOf("s")>-1?(parseFloat(duration)||0)*1e3:parseFloat(duration)||0}var WaDetails=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.animationGeneration=0,this.isAnimating=!1,this.open=!1,this.disabled=!1,this.appearance="outlined",this.iconPlacement="end"}disconnectedCallback(){super.disconnectedCallback(),this.detailsObserver?.disconnect()}firstUpdated(changedProperties){super.firstUpdated(changedProperties),this.body.style.height=this.open?"auto":"0",this.open&&(this.details.open=!0),this.detailsObserver=new MutationObserver(changes=>{for(let change of changes)change.type==="attributes"&&change.attributeName==="open"&&(this.details.open?this.show():this.hide())}),this.detailsObserver.observe(this.details,{attributes:!0})}updated(changedProperties){changedProperties.has("isAnimating")&&this.customStates.set("animating",this.isAnimating)}handleSummaryClick(event){event.composedPath().some(element=>{if(!(element instanceof HTMLElement))return!1;let tagName=element.tagName?.toLowerCase();return["a","button","input","textarea","select"].includes(tagName)?!0:element instanceof WebAwesomeFormAssociatedElement?!("disabled"in element)||!element.disabled:!1})||(event.preventDefault(),this.disabled||(this.open?this.hide():this.show(),this.header.focus()))}handleSummaryKeyDown(event){(event.key==="Enter"||event.key===" ")&&(event.preventDefault(),this.open?this.hide():this.show()),(event.key==="ArrowUp"||event.key==="ArrowLeft")&&(event.preventDefault(),this.hide()),(event.key==="ArrowDown"||event.key==="ArrowRight")&&(event.preventDefault(),this.show())}closeOthersWithSameName(){if(!this.name)return;this.getRootNode().querySelectorAll(`wa-details[name="${this.name}"]`).forEach(detail=>{detail!==this&&detail.open&&(detail.open=!1)})}async handleOpenChange(){this.animationGeneration++;let generation=this.animationGeneration;if(this.open){this.details.open=!0;let waShow=new WaShowEvent;if(this.dispatchEvent(waShow),waShow.defaultPrevented){this.open=!1,this.details.open=!1;return}this.closeOthersWithSameName(),this.isAnimating=!0;let duration=parseDuration(getComputedStyle(this.body).getPropertyValue("--show-duration"));if(await animate(this.body,[{height:"0",opacity:"0"},{height:`${this.body.scrollHeight}px`,opacity:"1"}],{duration,easing:"linear"}),this.animationGeneration!==generation)return;this.body.style.height="auto",this.isAnimating=!1,this.dispatchEvent(new WaAfterShowEvent)}else{let waHide=new WaHideEvent;if(this.dispatchEvent(waHide),waHide.defaultPrevented){this.details.open=!0,this.open=!0;return}this.isAnimating=!0;let duration=parseDuration(getComputedStyle(this.body).getPropertyValue("--hide-duration"));if(await animate(this.body,[{height:`${this.body.scrollHeight}px`,opacity:"1"},{height:"0",opacity:"0"}],{duration,easing:"linear"}),this.animationGeneration!==generation)return;this.body.style.height="0",this.isAnimating=!1,this.details.open=!1,this.dispatchEvent(new WaAfterHideEvent)}}async show(){if(!(this.open||this.disabled))return this.open=!0,waitForEvent(this,"wa-after-show")}async hide(){if(!(!this.open||this.disabled))return this.open=!1,waitForEvent(this,"wa-after-hide")}render(){let isRtl=this.hasUpdated?this.localize.dir()==="rtl":this.dir==="rtl";return b2`
      <details part="base details">
        <summary
          part="header"
          role="button"
          aria-expanded=${this.open?"true":"false"}
          aria-controls="content"
          aria-disabled=${this.disabled?"true":"false"}
          tabindex=${this.disabled?"-1":"0"}
          @click=${this.handleSummaryClick}
          @keydown=${this.handleSummaryKeyDown}
        >
          <slot name="summary" part="summary">${this.summary}</slot>

          <span part="icon">
            <slot name="expand-icon">
              <wa-icon library="system" variant="solid" name=${isRtl?"chevron-left":"chevron-right"}></wa-icon>
            </slot>
            <slot name="collapse-icon">
              <wa-icon library="system" variant="solid" name=${isRtl?"chevron-left":"chevron-right"}></wa-icon>
            </slot>
          </span>
        </summary>

        <div
          class=${e7({body:!0,animating:this.isAnimating})}
          role="region"
          aria-labelledby="header"
        >
          <slot part="content" id="content" class="content"></slot>
        </div>
      </details>
    `}};WaDetails.css=details_styles_default;__decorateClass([e5("details")],WaDetails.prototype,"details",2);__decorateClass([e5("summary")],WaDetails.prototype,"header",2);__decorateClass([e5(".body")],WaDetails.prototype,"body",2);__decorateClass([e5(".expand-icon-slot")],WaDetails.prototype,"expandIconSlot",2);__decorateClass([r5()],WaDetails.prototype,"isAnimating",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaDetails.prototype,"open",2);__decorateClass([n4()],WaDetails.prototype,"summary",2);__decorateClass([n4({reflect:!0})],WaDetails.prototype,"name",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaDetails.prototype,"disabled",2);__decorateClass([n4({reflect:!0})],WaDetails.prototype,"appearance",2);__decorateClass([n4({attribute:"icon-placement",reflect:!0})],WaDetails.prototype,"iconPlacement",2);__decorateClass([watch("open",{waitUntilFirstUpdate:!0})],WaDetails.prototype,"handleOpenChange",1);WaDetails=__decorateClass([t3("wa-details")],WaDetails);var RenderedWatcher=class{constructor(element,callback){this.element=element,this.callback=callback}start(...additionalTargets){if(!!1){this.observer??(this.observer=new ResizeObserver(()=>this.check())),this.observer.observe(this.element);for(let target of additionalTargets)this.observer.observe(target);this.initialCheckHandle??(this.initialCheckHandle=requestAnimationFrame(()=>{this.initialCheckHandle=void 0,this.check()}))}}stop(){this.initialCheckHandle!==void 0&&(cancelAnimationFrame(this.initialCheckHandle),this.initialCheckHandle=void 0),this.observer?.disconnect()}check(){this.callback(this.element.getClientRects().length>0)}};function getOffset(element,parent){return{top:Math.round(element.getBoundingClientRect().top-parent.getBoundingClientRect().top),left:Math.round(element.getBoundingClientRect().left-parent.getBoundingClientRect().left)}}function isEventInsideRect(event,el){let rect=el.getBoundingClientRect();return event.clientX>=rect.left&&event.clientX<=rect.right&&event.clientY>=rect.top&&event.clientY<=rect.bottom}var locks=new Set;function getScrollbarWidth(){let documentWidth=document.documentElement.clientWidth;return Math.abs(window.innerWidth-documentWidth)}function getExistingBodyPadding(){let padding=Number(getComputedStyle(document.body).paddingRight.replace(/px/,""));return isNaN(padding)||!padding?0:padding}function lockBodyScrolling(lockingEl){if(locks.add(lockingEl),!document.documentElement.classList.contains("wa-scroll-lock")){let scrollbarWidth=getScrollbarWidth()+getExistingBodyPadding(),scrollbarGutterProperty=getComputedStyle(document.documentElement).scrollbarGutter;(!scrollbarGutterProperty||scrollbarGutterProperty==="auto")&&(scrollbarGutterProperty="stable"),scrollbarWidth<2&&(scrollbarGutterProperty=""),document.documentElement.style.setProperty("--wa-scroll-lock-gutter",scrollbarGutterProperty),document.documentElement.classList.add("wa-scroll-lock"),document.documentElement.style.setProperty("--wa-scroll-lock-size",`${scrollbarWidth}px`)}}function unlockBodyScrolling(lockingEl){locks.delete(lockingEl),locks.size===0&&(document.documentElement.classList.remove("wa-scroll-lock"),document.documentElement.style.removeProperty("--wa-scroll-lock-size"))}function scrollIntoView(element,container,direction="vertical",behavior="smooth"){let offset3=getOffset(element,container),offsetTop=offset3.top+container.scrollTop,offsetLeft=offset3.left+container.scrollLeft,minX=container.scrollLeft,maxX=container.scrollLeft+container.offsetWidth,minY=container.scrollTop,maxY=container.scrollTop+container.offsetHeight;(direction==="horizontal"||direction==="both")&&(offsetLeft<minX?container.scrollTo({left:offsetLeft,behavior}):offsetLeft+element.clientWidth>maxX&&container.scrollTo({left:offsetLeft-container.offsetWidth+element.clientWidth,behavior})),(direction==="vertical"||direction==="both")&&(offsetTop<minY?container.scrollTo({top:offsetTop,behavior}):offsetTop+element.clientHeight>maxY&&container.scrollTo({top:offsetTop-container.offsetHeight+element.clientHeight,behavior}))}function parseSpaceDelimitedTokens(input){return input.split(" ").map(token=>token.trim()).filter(token=>token!=="")}var dialog_styles_default=i`
  :host {
    --width: 31rem;
    --spacing: var(--wa-space-l);
    --backdrop-filter: none;
    --show-duration: var(--wa-transition-normal);
    --hide-duration: var(--wa-transition-normal);

    display: none;
  }

  :host([open]) {
    display: block;
  }

  .dialog {
    display: flex;
    flex-direction: column;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    width: var(--width);
    max-width: calc(100% - var(--wa-space-2xl));
    max-height: calc(100% - var(--wa-space-2xl));
    color: inherit;
    background-color: var(--wa-color-surface-raised);
    border-radius: var(--wa-panel-border-radius);
    border: none;
    box-shadow: var(--wa-shadow-l);
    padding: 0;
    margin: auto;

    &.show {
      animation: show-dialog var(--show-duration) ease;

      &::backdrop {
        animation: show-backdrop var(--show-duration, 200ms) ease;
      }
    }

    &.hide {
      animation: show-dialog var(--hide-duration) ease reverse;

      &::backdrop {
        animation: show-backdrop var(--hide-duration, 200ms) ease reverse;
      }
    }

    &.pulse {
      animation: pulse 250ms ease;
    }
  }

  .dialog:focus {
    outline: none;
  }

  /* Ensure there's enough vertical padding for phones that don't update vh when chrome appears (e.g. iPhone) */
  @media screen and (max-width: 420px) {
    .dialog {
      max-height: 80vh;
    }
  }

  .open {
    display: flex;
    opacity: 1;
  }

  .header {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: nowrap;

    padding-inline-start: var(--spacing);
    padding-block-end: 0;

    /* Subtract the close button's padding so that the X is visually aligned with the edges of the dialog content */
    padding-inline-end: calc(var(--spacing) - var(--wa-form-control-padding-block));
    padding-block-start: calc(var(--spacing) - var(--wa-form-control-padding-block));
  }

  .title {
    align-self: center;
    flex: 1 1 auto;
    font-family: inherit;
    font-size: var(--wa-font-size-l);
    font-weight: var(--wa-font-weight-heading);
    line-height: var(--wa-line-height-condensed);
    margin: 0;
  }

  .header-actions {
    align-self: start;
    display: flex;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: end;
    gap: var(--wa-space-2xs);
    padding-inline-start: var(--spacing);
  }

  .header-actions wa-button,
  .header-actions ::slotted(wa-button) {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .body {
    flex: 1 1 auto;
    display: block;
    padding: var(--spacing);
    overflow: auto;
    -webkit-overflow-scrolling: touch;

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  .footer {
    flex: 0 0 auto;
    display: flex;
    flex-wrap: wrap;
    gap: var(--wa-space-xs);
    justify-content: end;
    padding: var(--spacing);
    padding-block-start: 0;
  }

  .footer ::slotted(wa-button:not(:first-of-type)) {
    margin-inline-start: var(--wa-spacing-xs);
  }

  .dialog::backdrop {
    /*
      NOTE: the ::backdrop element doesn't inherit properly in Safari yet, but it will in 17.4! At that time, we can
      remove the fallback values here.
    */
    background-color: var(--wa-color-overlay-modal, rgb(0 0 0 / 0.25));
    backdrop-filter: var(--backdrop-filter);
  }

  @keyframes pulse {
    0% {
      scale: 1;
    }
    50% {
      scale: 1.02;
    }
    100% {
      scale: 1;
    }
  }

  @keyframes show-dialog {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }

  @keyframes show-backdrop {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (forced-colors: active) {
    .dialog {
      border: solid 1px white;
    }
  }
`;var dismissibleStack=[];function registerDismissible(key){unregisterDismissible(key),dismissibleStack.push(key)}function unregisterDismissible(key){for(let i8=dismissibleStack.length-1;i8>=0;i8--)if(dismissibleStack[i8]===key){dismissibleStack.splice(i8,1);break}}function isTopDismissible(key){return dismissibleStack.length>0&&dismissibleStack[dismissibleStack.length-1]===key}var WaDialog=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.hasSlotController=new HasSlotController(this,"footer","header-actions","label"),this.renderedWatcher=new RenderedWatcher(this,isRendered=>this.handleRenderedChange(isRendered)),this.open=!1,this.label="",this.withoutHeader=!1,this.lightDismiss=!1,this.withFooter=!1,this.withLabel=!1,this.handleDocumentKeyDown=event=>{event.key==="Escape"&&this.open&&isTopDismissible(this)&&(event.preventDefault(),event.stopPropagation(),this.requestClose(this.dialog))}}firstUpdated(changedProperties){super.firstUpdated(changedProperties),this.open&&(this.addOpenListeners(),this.dialog.showModal(),lockBodyScrolling(this),this.renderedWatcher.start(this.dialog))}disconnectedCallback(){super.disconnectedCallback(),this.renderedWatcher.stop(),unlockBodyScrolling(this),this.removeOpenListeners()}async requestClose(source){let waHideEvent=new WaHideEvent({source});if(this.dispatchEvent(waHideEvent),waHideEvent.defaultPrevented){this.open=!0,animateWithClass(this.dialog,"pulse");return}this.removeOpenListeners(),await animateWithClass(this.dialog,"hide"),this.open=!1,this.dialog.close(),unlockBodyScrolling(this),this.renderedWatcher.stop();let trigger=this.originalTrigger;typeof trigger?.focus=="function"&&setTimeout(()=>trigger.focus()),this.dispatchEvent(new WaAfterHideEvent)}addOpenListeners(){document.addEventListener("keydown",this.handleDocumentKeyDown),registerDismissible(this)}removeOpenListeners(){document.removeEventListener("keydown",this.handleDocumentKeyDown),unregisterDismissible(this)}handleDialogCancel(event){event.preventDefault(),!this.dialog.classList.contains("hide")&&event.target===this.dialog&&isTopDismissible(this)&&this.requestClose(this.dialog)}handleDialogClick(event){let button=event.target.closest('[data-dialog="close"]');button&&(event.stopPropagation(),this.requestClose(button))}async handleDialogPointerDown(event){event.target===this.dialog&&!isEventInsideRect(event,this.dialog)&&(this.lightDismiss?this.requestClose(this.dialog):await animateWithClass(this.dialog,"pulse"))}handleRenderedChange(isRendered){if(!this.open){this.renderedWatcher.stop();return}!isRendered&&this.dialog.open?(this.removeOpenListeners(),this.dialog.close(),unlockBodyScrolling(this)):isRendered&&!this.dialog.open&&(this.addOpenListeners(),this.dialog.showModal(),lockBodyScrolling(this))}handleOpenChange(){this.open&&!this.dialog.open?this.show():!this.open&&this.dialog.open?(this.open=!0,this.requestClose(this.dialog)):this.open||this.renderedWatcher.stop()}async show(){let waShowEvent=new WaShowEvent;if(this.dispatchEvent(waShowEvent),waShowEvent.defaultPrevented){this.open=!1;return}this.addOpenListeners(),this.originalTrigger=document.activeElement,this.open=!0,this.dialog.showModal(),lockBodyScrolling(this),this.renderedWatcher.start(this.dialog),requestAnimationFrame(()=>{let elementToFocus=this.querySelector("[autofocus]");elementToFocus&&typeof elementToFocus.focus=="function"?elementToFocus.focus():this.dialog.focus()}),await animateWithClass(this.dialog,"show"),this.dispatchEvent(new WaAfterShowEvent)}render(){let hasHeader=!this.withoutHeader,hasFooter=this.hasSlotController.test("footer","withFooter"),hasLabel=this.label.length>0||this.hasSlotController.test("label","withLabel");return b2`
      <dialog
        part="dialog"
        aria-labelledby=${o7(hasHeader&&hasLabel?"title":void 0)}
        aria-label=${o7(!hasHeader&&this.label?this.label:void 0)}
        class=${e7({dialog:!0,open:this.open})}
        @cancel=${this.handleDialogCancel}
        @click=${this.handleDialogClick}
        @pointerdown=${this.handleDialogPointerDown}
      >
        ${hasHeader?b2`
              <div part="header" class="header">
                <h2 part="title" class="title" id="title">
                  <!-- If there's no label, use an invisible character to prevent the header from collapsing -->
                  <slot name="label"> ${this.label.length>0?this.label:"\u200B"} </slot>
                </h2>
                <div part="header-actions" class="header-actions">
                  <slot name="header-actions"></slot>
                  <wa-button
                    part="close-button"
                    exportparts="base:close-button__base"
                    class="close"
                    appearance="plain"
                    @click="${event=>this.requestClose(event.target)}"
                  >
                    <wa-icon
                      name="xmark"
                      label=${this.localize.term("close")}
                      library="system"
                      variant="solid"
                    ></wa-icon>
                  </wa-button>
                </div>
              </div>
            `:""}

        <div part="body" class="body"><slot></slot></div>

        <!-- Use a hidden element so we still get "slotchange" events. -->
        <div part="footer" class="footer" ?hidden=${!hasFooter}>
          <slot name="footer"></slot>
        </div>
      </dialog>
    `}};WaDialog.css=dialog_styles_default;__decorateClass([e5(".dialog")],WaDialog.prototype,"dialog",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaDialog.prototype,"open",2);__decorateClass([n4({reflect:!0})],WaDialog.prototype,"label",2);__decorateClass([n4({attribute:"without-header",type:Boolean,reflect:!0})],WaDialog.prototype,"withoutHeader",2);__decorateClass([n4({attribute:"light-dismiss",type:Boolean})],WaDialog.prototype,"lightDismiss",2);__decorateClass([n4({attribute:"with-footer",type:Boolean})],WaDialog.prototype,"withFooter",2);__decorateClass([n4({attribute:"with-label",type:Boolean})],WaDialog.prototype,"withLabel",2);__decorateClass([watch("open",{waitUntilFirstUpdate:!0})],WaDialog.prototype,"handleOpenChange",1);WaDialog=__decorateClass([t3("wa-dialog")],WaDialog);document.addEventListener("click",event=>{let dialogAttrEl=event.target.closest("[data-dialog]");if(dialogAttrEl instanceof Element){let[command,id3]=parseSpaceDelimitedTokens(dialogAttrEl.getAttribute("data-dialog")||"");if(command==="open"&&id3?.length){let dialog=dialogAttrEl.getRootNode().getElementById(id3);dialog?.localName==="wa-dialog"?dialog.open=!0:console.warn(`A dialog with an ID of "${id3}" could not be found in this document.`)}}}),document.addEventListener("pointerdown",()=>{});var divider_styles_default=i`
  :host {
    --color: var(--wa-color-surface-border);
    --width: var(--wa-border-width-s);
    --spacing: var(--wa-space-m);
    --label-spacing: var(--wa-space-s);
    --label-offset: 0;
  }

  :host(:not([orientation='vertical'])) {
    display: block;
    border-top: solid var(--width) var(--color);
    margin: var(--spacing) 0;
  }

  :host([orientation='vertical']) {
    display: inline-block;
    height: 100%;
    border-inline-start: solid var(--width) var(--color);
    margin: 0 var(--spacing);
    min-block-size: 1lh;
  }

  /* With a label, the host's border gives way to two lines that flank the label */
  :host([with-label]) {
    align-items: center;
    gap: var(--label-spacing);
    border: none;
  }

  :host([with-label]:not([orientation='vertical'])) {
    display: flex;
  }

  :host([with-label][orientation='vertical']) {
    display: inline-flex;
    flex-direction: column;
  }

  :host([with-label])::before,
  :host([with-label])::after {
    content: '';
    flex: 1 1 0;
  }

  :host([with-label]:not([orientation='vertical']))::before,
  :host([with-label]:not([orientation='vertical']))::after {
    min-inline-size: 1em;
    border-top: solid var(--width) var(--color);
  }

  :host([with-label][orientation='vertical'])::before,
  :host([with-label][orientation='vertical'])::after {
    min-block-size: 1lh;
    border-inline-start: solid var(--width) var(--color);
  }

  :host([with-label][label-placement='start'])::before,
  :host([with-label][label-placement='end'])::after {
    flex: 0 0 var(--label-offset);
    min-inline-size: 0;
    min-block-size: 0;
  }

  :host(:not([with-label])) .label {
    display: none;
  }

  :host([with-label]) .label {
    display: inline-flex;
    align-items: center;
    gap: var(--wa-space-2xs);
    flex: 0 1 auto;
    color: var(--wa-color-text-quiet);
    font-size: var(--wa-font-size-s);
    line-height: var(--wa-line-height-condensed);
    text-align: center;
  }
`;var WaDivider=class extends WebAwesomeElement{constructor(){super(...arguments),this.hasSlotController=new HasSlotController(this,"[default]"),this.orientation="horizontal",this.withLabel=!1,this.labelPlacement="center"}connectedCallback(){super.connectedCallback(),this.setAttribute("role","separator")}willUpdate(changedProperties){this.withLabel=this.hasSlotController.test("[default]","withLabel"),super.willUpdate(changedProperties)}handleVerticalChange(){this.setAttribute("aria-orientation",this.orientation)}handleSlotChange(){this.internals&&(this.internals.ariaLabel=this.textContent?.trim()||null)}render(){return b2`
      <div part="label" class="label">
        <slot @slotchange=${this.handleSlotChange}></slot>
      </div>
    `}};WaDivider.css=divider_styles_default;__decorateClass([n4({reflect:!0})],WaDivider.prototype,"orientation",2);__decorateClass([n4({attribute:"with-label",type:Boolean,reflect:!0})],WaDivider.prototype,"withLabel",2);__decorateClass([n4({attribute:"label-placement",reflect:!0})],WaDivider.prototype,"labelPlacement",2);__decorateClass([watch("orientation")],WaDivider.prototype,"handleVerticalChange",1);WaDivider=__decorateClass([t3("wa-divider")],WaDivider);var drawer_styles_default=i`
  :host {
    --size: 25rem;
    --spacing: var(--wa-space-l);
    --backdrop-filter: none;
    --show-duration: var(--wa-transition-normal);
    --hide-duration: var(--wa-transition-normal);

    display: none;
  }

  :host([open]) {
    display: block;
  }

  .drawer {
    display: flex;
    flex-direction: column;
    top: 0;
    inset-inline-start: 0;
    width: 100%;
    height: 100%;
    max-width: 100%;
    max-height: 100%;
    overflow: hidden;
    color: inherit;
    background-color: var(--wa-color-surface-raised);
    border: none;
    box-shadow: var(--wa-shadow-l);
    overflow: auto;
    padding: 0;
    margin: 0;
    animation-duration: var(--show-duration);
    animation-timing-function: ease;

    &.show::backdrop {
      animation: show-backdrop var(--show-duration, 200ms) ease;
    }

    &.hide::backdrop {
      animation: show-backdrop var(--hide-duration, 200ms) ease reverse;
    }

    &.show.top {
      animation: show-drawer-from-top var(--show-duration) ease;
    }

    &.hide.top {
      animation: show-drawer-from-top var(--hide-duration) ease reverse;
    }

    &.show.end {
      animation: show-drawer-from-end var(--show-duration) ease;

      &:dir(rtl) {
        animation-name: show-drawer-from-start;
      }
    }

    &.hide.end {
      animation: show-drawer-from-end var(--hide-duration) ease reverse;

      &:dir(rtl) {
        animation-name: show-drawer-from-start;
      }
    }

    &.show.bottom {
      animation: show-drawer-from-bottom var(--show-duration) ease;
    }

    &.hide.bottom {
      animation: show-drawer-from-bottom var(--hide-duration) ease reverse;
    }

    &.show.start {
      animation: show-drawer-from-start var(--show-duration) ease;

      &:dir(rtl) {
        animation-name: show-drawer-from-end;
      }
    }

    &.hide.start {
      animation: show-drawer-from-start var(--hide-duration) ease reverse;

      &:dir(rtl) {
        animation-name: show-drawer-from-end;
      }
    }

    &.pulse {
      animation: pulse 250ms ease;
    }
  }

  .drawer:focus {
    outline: none;
  }

  .top {
    top: 0;
    inset-inline-end: auto;
    bottom: auto;
    inset-inline-start: 0;
    width: 100%;
    height: var(--size);
  }

  .end {
    top: 0;
    inset-inline-end: 0;
    bottom: auto;
    inset-inline-start: auto;
    width: var(--size);
    height: 100%;
  }

  .bottom {
    top: auto;
    inset-inline-end: auto;
    bottom: 0;
    inset-inline-start: 0;
    width: 100%;
    height: var(--size);
  }

  .start {
    top: 0;
    inset-inline-end: auto;
    bottom: auto;
    inset-inline-start: 0;
    width: var(--size);
    height: 100%;
  }

  .header {
    display: flex;
    flex-wrap: nowrap;
    padding-inline-start: var(--spacing);
    padding-block-end: 0;

    /* Subtract the close button's padding so that the X is visually aligned with the edges of the dialog content */
    padding-inline-end: calc(var(--spacing) - var(--wa-form-control-padding-block));
    padding-block-start: calc(var(--spacing) - var(--wa-form-control-padding-block));
  }

  .title {
    align-self: center;
    flex: 1 1 auto;
    font: inherit;
    font-size: var(--wa-font-size-l);
    font-weight: var(--wa-font-weight-heading);
    line-height: var(--wa-line-height-condensed);
    margin: 0;
  }

  .header-actions {
    align-self: start;
    display: flex;
    flex-shrink: 0;
    flex-wrap: wrap;
    justify-content: end;
    gap: var(--wa-space-2xs);
    padding-inline-start: var(--spacing);
  }

  .header-actions wa-button,
  .header-actions ::slotted(wa-button) {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .body {
    flex: 1 1 auto;
    display: block;
    padding: var(--spacing);
    overflow: auto;
    -webkit-overflow-scrolling: touch;

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  .footer {
    display: flex;
    flex-wrap: wrap;
    gap: var(--wa-space-xs);
    justify-content: end;
    padding: var(--spacing);
    padding-block-start: 0;
  }

  .footer ::slotted(wa-button:not(:last-of-type)) {
    margin-inline-end: var(--wa-spacing-xs);
  }

  .drawer::backdrop {
    /*
        NOTE: the ::backdrop element doesn't inherit properly in Safari yet, but it will in 17.4! At that time, we can
        remove the fallback values here.
      */
    background-color: var(--wa-color-overlay-modal, rgb(0 0 0 / 0.25));
    backdrop-filter: var(--backdrop-filter);
  }

  @keyframes pulse {
    0% {
      scale: 1;
    }
    50% {
      scale: 1.01;
    }
    100% {
      scale: 1;
    }
  }

  @keyframes show-drawer {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }

  @keyframes show-drawer-from-top {
    from {
      opacity: 0;
      translate: 0 -100%;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  @keyframes show-drawer-from-end {
    from {
      opacity: 0;
      translate: 100%;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  @keyframes show-drawer-from-bottom {
    from {
      opacity: 0;
      translate: 0 100%;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  @keyframes show-drawer-from-start {
    from {
      opacity: 0;
      translate: -100% 0;
    }
    to {
      opacity: 1;
      translate: 0 0;
    }
  }

  @keyframes show-backdrop {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  @media (forced-colors: active) {
    .drawer {
      border: solid 1px white;
    }
  }
`;var WaDrawer=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.hasSlotController=new HasSlotController(this,"footer","header-actions","label"),this.renderedWatcher=new RenderedWatcher(this,isRendered=>this.handleRenderedChange(isRendered)),this.open=!1,this.label="",this.placement="end",this.withoutHeader=!1,this.lightDismiss=!1,this.withFooter=!1,this.withLabel=!1,this.handleDocumentKeyDown=event=>{event.key==="Escape"&&this.open&&isTopDismissible(this)&&(event.preventDefault(),event.stopPropagation(),this.requestClose(this.drawer))}}firstUpdated(changedProperties){super.firstUpdated(changedProperties),this.open&&(this.addOpenListeners(),this.drawer.showModal(),lockBodyScrolling(this),this.renderedWatcher.start(this.drawer))}disconnectedCallback(){super.disconnectedCallback(),this.renderedWatcher.stop(),unlockBodyScrolling(this),this.removeOpenListeners()}async requestClose(source){let waHideEvent=new WaHideEvent({source});if(this.dispatchEvent(waHideEvent),waHideEvent.defaultPrevented){this.open=!0,animateWithClass(this.drawer,"pulse");return}this.removeOpenListeners(),await animateWithClass(this.drawer,"hide"),this.open=!1,this.drawer.close(),unlockBodyScrolling(this),this.renderedWatcher.stop();let trigger=this.originalTrigger;typeof trigger?.focus=="function"&&setTimeout(()=>trigger.focus()),this.dispatchEvent(new WaAfterHideEvent)}addOpenListeners(){document.addEventListener("keydown",this.handleDocumentKeyDown),registerDismissible(this)}removeOpenListeners(){document.removeEventListener("keydown",this.handleDocumentKeyDown),unregisterDismissible(this)}handleDialogCancel(event){event.preventDefault(),!this.drawer.classList.contains("hide")&&event.target===this.drawer&&isTopDismissible(this)&&this.requestClose(this.drawer)}handleDialogClick(event){let button=event.target.closest('[data-drawer="close"]');button&&(event.stopPropagation(),this.requestClose(button))}async handleDialogPointerDown(event){event.target===this.drawer&&!isEventInsideRect(event,this.drawer)&&(this.lightDismiss?this.requestClose(this.drawer):await animateWithClass(this.drawer,"pulse"))}handleRenderedChange(isRendered){if(!this.open){this.renderedWatcher.stop();return}!isRendered&&this.drawer.open?(this.removeOpenListeners(),this.drawer.close(),unlockBodyScrolling(this)):isRendered&&!this.drawer.open&&(this.addOpenListeners(),this.drawer.showModal(),lockBodyScrolling(this))}handleOpenChange(){this.open&&!this.drawer.open?this.show():this.drawer.open?(this.open=!0,this.requestClose(this.drawer)):this.open||this.renderedWatcher.stop()}async show(){let waShowEvent=new WaShowEvent;if(this.dispatchEvent(waShowEvent),waShowEvent.defaultPrevented){this.open=!1;return}this.addOpenListeners(),this.originalTrigger=document.activeElement,this.open=!0,this.drawer.showModal(),lockBodyScrolling(this),this.renderedWatcher.start(this.drawer),requestAnimationFrame(()=>{let elementToFocus=this.querySelector("[autofocus]");elementToFocus&&typeof elementToFocus.focus=="function"?elementToFocus.focus():this.drawer.focus()}),await animateWithClass(this.drawer,"show"),this.dispatchEvent(new WaAfterShowEvent)}render(){let hasHeader=!this.withoutHeader,hasFooter=this.hasSlotController.test("footer","withFooter"),hasLabel=this.label.length>0||this.hasSlotController.test("label","withLabel");return b2`
      <dialog
        part="dialog"
        aria-labelledby=${o7(hasHeader&&hasLabel?"title":void 0)}
        aria-label=${o7(!hasHeader&&this.label?this.label:void 0)}
        class=${e7({drawer:!0,open:this.open,top:this.placement==="top",end:this.placement==="end",bottom:this.placement==="bottom",start:this.placement==="start"})}
        @cancel=${this.handleDialogCancel}
        @click=${this.handleDialogClick}
        @pointerdown=${this.handleDialogPointerDown}
      >
        ${hasHeader?b2`
              <div part="header" class="header">
                <h2 part="title" class="title" id="title">
                  <!-- If there's no label, use an invisible character to prevent the header from collapsing -->
                  <slot name="label"> ${this.label.length>0?this.label:"\u200B"} </slot>
                </h2>
                <div part="header-actions" class="header-actions">
                  <slot name="header-actions"></slot>
                  <wa-button
                    part="close-button"
                    exportparts="base:close-button__base"
                    class="close"
                    appearance="plain"
                    @click="${event=>this.requestClose(event.target)}"
                  >
                    <wa-icon
                      name="xmark"
                      label=${this.localize.term("close")}
                      library="system"
                      variant="solid"
                    ></wa-icon>
                  </wa-button>
                </div>
              </div>
            `:""}

        <div part="body" class="body"><slot></slot></div>

        <div part="footer" class="footer" ?hidden=${!hasFooter}>
          <slot name="footer"></slot>
        </div>
      </dialog>
    `}};WaDrawer.css=drawer_styles_default;__decorateClass([e5(".drawer")],WaDrawer.prototype,"drawer",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaDrawer.prototype,"open",2);__decorateClass([n4({reflect:!0})],WaDrawer.prototype,"label",2);__decorateClass([n4({reflect:!0})],WaDrawer.prototype,"placement",2);__decorateClass([n4({attribute:"without-header",type:Boolean,reflect:!0})],WaDrawer.prototype,"withoutHeader",2);__decorateClass([n4({attribute:"light-dismiss",type:Boolean})],WaDrawer.prototype,"lightDismiss",2);__decorateClass([n4({attribute:"with-footer",type:Boolean})],WaDrawer.prototype,"withFooter",2);__decorateClass([n4({attribute:"with-label",type:Boolean})],WaDrawer.prototype,"withLabel",2);__decorateClass([watch("open",{waitUntilFirstUpdate:!0})],WaDrawer.prototype,"handleOpenChange",1);WaDrawer=__decorateClass([t3("wa-drawer")],WaDrawer);document.addEventListener("click",event=>{let drawerAttrEl=event.target.closest("[data-drawer]");if(drawerAttrEl instanceof Element){let[command,id3]=parseSpaceDelimitedTokens(drawerAttrEl.getAttribute("data-drawer")||"");if(command==="open"&&id3?.length){let drawer=drawerAttrEl.getRootNode().getElementById(id3);drawer?.localName==="wa-drawer"?drawer.open=!0:console.warn(`A drawer with an ID of "${id3}" could not be found in this document.`)}}}),document.addEventListener("pointerdown",()=>{});var WaClearEvent=class extends Event{constructor(){super("wa-clear",{bubbles:!0,cancelable:!1,composed:!0})}};function submitOnEnter(event,el){let hasModifier=event.metaKey||event.ctrlKey||event.shiftKey||event.altKey;event.key==="Enter"&&!hasModifier&&setTimeout(()=>{!event.defaultPrevented&&!event.isComposing&&submitForm(el)})}var submittableTags=new Map([["input",!0],["wa-input",!0],["wa-tag-input",!0],["wa-number-input",!0],["wa-otp-input",!0],["wa-slider",!0]]),submittableTypes=new Map([["button",!1],["checkbox",!1],["color",!1],["date",!1],["datetime-local",!1],["email",!0],["file",!1],["hidden",!1],["image",!1],["month",!1],["number",!0],["password",!0],["radio",!1],["range",!1],["reset",!0],["search",!0],["submit",!1],["tel",!0],["text",!0],["time",!1],["url",!0],["week",!1]]),isSubmittableElement=el=>{let tagName=el?.localName;if(!tagName||!!!submittableTags.get(tagName))return!1;if(tagName!=="input"&&tagName!=="wa-input")return!0;let type=el.type;return!!submittableTypes.get(type)};function submitForm(el){let form=null;if("form"in el&&(form=el.form),!form&&"getForm"in el&&(form=el.getForm()),!form)return;let formElements=Array.from(form.elements),submittableFormElements=0;for(let el2 of formElements)isSubmittableElement(el2)&&(submittableFormElements+=1);if(submittableFormElements===1){form.requestSubmit(null);return}let button=formElements.find(el2=>el2.type==="submit"&&!el2.matches(":disabled"));button&&(["input","button"].includes(button.localName)?form.requestSubmit(button):button.click())}var input_styles_default=i`
  :host {
    border-width: 0;
  }

  :host(:focus) {
    outline: none;
  }

  .text-field {
    display: flex;
    align-items: stretch;
    justify-content: start;
    position: relative;
    transition: inherit;
    height: var(--wa-form-control-height);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    cursor: text;
    color: var(--wa-form-control-value-color);
    font-size: var(--wa-form-control-value-font-size);
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    vertical-align: middle;
    width: 100%;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    background-color: var(--wa-form-control-background-color);
    box-shadow: var(--box-shadow);
    padding: 0 var(--wa-form-control-padding-inline);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Only ring the field when the text input has focus, not inner buttons */
    &:has(input:focus, textarea:focus) {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled inputs */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .text-field {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .text-field {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  :host([pill]) .text-field {
    border-radius: var(--wa-border-radius-pill) !important;
  }

  .text-field {
    /* Show autofill styles over the entire text field, not just the native <input> */
    &:has(:autofill),
    &:has(:-webkit-autofill) {
      background-color: var(--wa-color-brand-fill-quiet) !important;
    }

    input,
    textarea {
      /*
      Fixes an alignment issue with placeholders.
      https://github.com/shoelace-style/webawesome/issues/342
    */
      height: 100%;

      padding: 0;
      border: none;
      outline: none;
      box-shadow: none;
      margin: 0;
      cursor: inherit;
      -webkit-appearance: none;
      font: inherit;

      /* Turn off Safari's autofill styles */
      &:-webkit-autofill,
      &:-webkit-autofill:hover,
      &:-webkit-autofill:focus,
      &:-webkit-autofill:active {
        -webkit-background-clip: text;
        background-color: transparent;
        -webkit-text-fill-color: inherit;
      }
    }
  }

  input {
    flex: 1 1 auto;
    min-width: 0;
    height: 100%;
    transition: inherit;

    /* prettier-ignore */
    background-color: rgb(118 118 118 / 0); /* ensures proper placeholder styles in webkit's date input */
    height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    padding-block: 0;
    color: inherit;

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &::-webkit-search-decoration,
    &::-webkit-search-cancel-button,
    &::-webkit-search-results-button,
    &::-webkit-search-results-decoration {
      -webkit-appearance: none;
    }

    &:focus {
      outline: none;
    }
  }

  textarea {
    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }
  }

  .start,
  .end {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    cursor: default;

    &::slotted(wa-icon) {
      color: var(--wa-color-neutral-on-quiet);
    }
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  /*
   * Clearable + Password Toggle
   */

  .clear,
  .password-toggle {
    position: relative;
    display: inline-flex;
    align-self: center;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    height: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    border-radius: var(--wa-border-radius-s);
    background: none;
    padding: 0;
    transition: var(--wa-transition-normal) color;
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half of that growth on each side. Keeps the
       glyph flush with the field's trailing padding edge, like every other form control. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &::after {
      content: '';
      position: absolute;
      inset-inline: 0;
      height: var(--wa-form-control-height);
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }

    &:focus {
      outline: none;
    }

    &:focus-visible {
      outline: var(--wa-focus-ring);
      outline-offset: var(--wa-focus-ring-offset);
    }
  }

  /* Don't show the browser's password toggle in Edge */
  ::-ms-reveal {
    display: none;
  }

  /* Hide the built-in number spinner */
  :host([without-spin-buttons]) input[type='number'] {
    -moz-appearance: textfield;

    &::-webkit-outer-spin-button,
    &::-webkit-inner-spin-button {
      -webkit-appearance: none;
      display: none;
    }
  }
`;var WaInput=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.hasSlotController=new HasSlotController(this,"hint","label"),this.localize=new LocalizeController2(this),this.title="",this.type="text",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.size="m",this.appearance="outlined",this.pill=!1,this.label="",this.hint="",this.withClear=!1,this.placeholder="",this.readonly=!1,this.passwordToggle=!1,this.passwordVisible=!1,this.withoutSpinButtons=!1,this.required=!1,this.spellcheck=!0,this.withLabel=!1,this.withHint=!1}static get validators(){return[...super.validators,MirrorValidator()]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(val){this._value!==val&&(this.valueHasChanged=!0,this._value=val)}updateFormValue(value){if(value==null){this.setValue("",null);return}super.updateFormValue(value)}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}handleChange(event){this.value=this.input.value,this.relayNativeEvent(event,{bubbles:!0,composed:!0})}handleClearClick(event){event.preventDefault(),this.value!==""&&(this.value="",this.updateComplete.then(()=>{this.dispatchEvent(new WaClearEvent),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})),this.input.focus()}handleInput(){this.value=this.input.value}handleKeyDown(event){submitOnEnter(event,this)}handlePasswordToggle(){this.passwordVisible=!this.passwordVisible}updated(changedProperties){if(super.updated(changedProperties),changedProperties.has("value")||changedProperties.has("defaultValue")||changedProperties.has("type")){let sanitizingTypes=["number","date","time","datetime-local"];this.input&&sanitizingTypes.includes(this.type)&&this.value&&this.input.value!==this.value&&(this._value=this.input.value),this.customStates.set("blank",!this.value),this.updateValidity()}}handleStepChange(){this.input.step=String(this.step),this.updateValidity()}focus(options){this.input.focus(options)}blur(){this.input.blur()}select(){this.input.select()}setSelectionRange(selectionStart,selectionEnd,selectionDirection="none"){this.input.setSelectionRange(selectionStart,selectionEnd,selectionDirection)}setRangeText(replacement,start,end,selectMode="preserve"){let selectionStart=start??this.input.selectionStart,selectionEnd=end??this.input.selectionEnd;this.input.setRangeText(replacement,selectionStart,selectionEnd,selectMode),this.value!==this.input.value&&(this.value=this.input.value)}showPicker(){"showPicker"in HTMLInputElement.prototype&&this.input.showPicker()}stepUp(){this.input.stepUp(),this.value!==this.input.value&&(this.value=this.input.value)}stepDown(){this.input.stepDown(),this.value!==this.input.value&&(this.value=this.input.value)}formResetCallback(){this.value=null,this.input&&(this.input.value=this.value),super.formResetCallback()}render(){let hasLabelSlot=this.hasSlotController.test("label","withLabel"),hasHintSlot=this.hasSlotController.test("hint","withHint"),hasLabel=this.label?!0:!!hasLabelSlot,hasHint=this.hint?!0:!!hasHintSlot,hasClearIcon=this.withClear&&!this.disabled&&!this.readonly,isClearIconVisible=(!this.didSSR||this.hasUpdated)&&hasClearIcon&&(typeof this.value=="number"||this.value&&this.value.length>0);return b2`
      <label
        part="form-control-label label"
        class=${e7({label:!0,"has-label":hasLabel})}
        for="input"
        aria-hidden=${hasLabel?"false":"true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base input-wrapper" class="text-field">
        <slot name="start" part="start" class="start"></slot>

        <input
          part="input"
          id="input"
          class="control"
          type=${this.type==="password"&&this.passwordVisible?"text":this.type}
          title=${this.title}
          name=${o7(this.name)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${o7(this.placeholder)}
          minlength=${o7(this.minlength)}
          maxlength=${o7(this.maxlength)}
          min=${o7(this.min)}
          max=${o7(this.max)}
          step=${o7(this.step)}
          .value=${l5(this.value??"")}
          autocapitalize=${o7(this.autocapitalize)}
          autocomplete=${o7(this.autocomplete)}
          autocorrect=${this.autocorrect?"on":"off"}
          ?autofocus=${this.autofocus}
          spellcheck=${this.spellcheck}
          pattern=${o7(this.pattern)}
          enterkeyhint=${o7(this.enterkeyhint)}
          inputmode=${o7(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @keydown=${this.handleKeyDown}
        />

        ${isClearIconVisible?b2`
              <button
                part="clear-button"
                class="clear"
                type="button"
                aria-label=${this.localize.term("clearEntry")}
                @click=${this.handleClearClick}
                tabindex="-1"
              >
                <slot name="clear-icon">
                  <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                </slot>
              </button>
            `:""}
        ${this.passwordToggle&&!this.disabled?b2`
              <button
                part="password-toggle-button"
                class="password-toggle"
                type="button"
                aria-label=${this.localize.term(this.passwordVisible?"hidePassword":"showPassword")}
                @click=${this.handlePasswordToggle}
              >
                ${this.passwordVisible?b2`
                      <slot name="hide-password-icon">
                        <wa-icon name="eye-slash" library="system" variant="regular"></wa-icon>
                      </slot>
                    `:b2`
                      <slot name="show-password-icon">
                        <wa-icon name="eye" library="system" variant="regular"></wa-icon>
                      </slot>
                    `}
              </button>
            `:""}

        <slot name="end" part="end" class="end"></slot>
      </div>

      <slot
        id="hint"
        part="hint"
        name="hint"
        class=${e7({"has-slotted":hasHint})}
        aria-hidden=${hasHint?"false":"true"}
        >${this.hint}</slot
      >
    `}};WaInput.css=[size_styles_default,form_control_styles_default,input_styles_default];WaInput.shadowRootOptions={...WebAwesomeFormAssociatedElement.shadowRootOptions,delegatesFocus:!0};__decorateClass([e5("input")],WaInput.prototype,"input",2);__decorateClass([n4()],WaInput.prototype,"title",2);__decorateClass([n4({reflect:!0})],WaInput.prototype,"type",2);__decorateClass([r5()],WaInput.prototype,"value",1);__decorateClass([n4({attribute:"value",reflect:!0})],WaInput.prototype,"defaultValue",2);__decorateClass([n4({reflect:!0})],WaInput.prototype,"size",2);__decorateClass([watch("size")],WaInput.prototype,"handleSizeChange",1);__decorateClass([n4({reflect:!0})],WaInput.prototype,"appearance",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaInput.prototype,"pill",2);__decorateClass([n4()],WaInput.prototype,"label",2);__decorateClass([n4({attribute:"hint"})],WaInput.prototype,"hint",2);__decorateClass([n4({attribute:"with-clear",type:Boolean})],WaInput.prototype,"withClear",2);__decorateClass([n4()],WaInput.prototype,"placeholder",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaInput.prototype,"readonly",2);__decorateClass([n4({attribute:"password-toggle",type:Boolean})],WaInput.prototype,"passwordToggle",2);__decorateClass([n4({attribute:"password-visible",type:Boolean})],WaInput.prototype,"passwordVisible",2);__decorateClass([n4({attribute:"without-spin-buttons",type:Boolean,reflect:!0})],WaInput.prototype,"withoutSpinButtons",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaInput.prototype,"required",2);__decorateClass([n4()],WaInput.prototype,"pattern",2);__decorateClass([n4({type:Number})],WaInput.prototype,"minlength",2);__decorateClass([n4({type:Number})],WaInput.prototype,"maxlength",2);__decorateClass([n4()],WaInput.prototype,"min",2);__decorateClass([n4()],WaInput.prototype,"max",2);__decorateClass([n4()],WaInput.prototype,"step",2);__decorateClass([n4()],WaInput.prototype,"autocapitalize",2);__decorateClass([n4({type:Boolean,converter:{fromAttribute:value=>!(!value||value==="off"),toAttribute:value=>value?"on":"off"}})],WaInput.prototype,"autocorrect",2);__decorateClass([n4()],WaInput.prototype,"autocomplete",2);__decorateClass([n4({type:Boolean})],WaInput.prototype,"autofocus",2);__decorateClass([n4()],WaInput.prototype,"enterkeyhint",2);__decorateClass([n4({type:Boolean,converter:{fromAttribute:value=>!(!value||value==="false"),toAttribute:value=>value?"true":"false"}})],WaInput.prototype,"spellcheck",2);__decorateClass([n4()],WaInput.prototype,"inputmode",2);__decorateClass([n4({attribute:"with-label",type:Boolean})],WaInput.prototype,"withLabel",2);__decorateClass([n4({attribute:"with-hint",type:Boolean})],WaInput.prototype,"withHint",2);__decorateClass([watch("step",{waitUntilFirstUpdate:!0})],WaInput.prototype,"handleStepChange",1);WaInput=__decorateClass([t3("wa-input")],WaInput);WaInput.disableWarning?.("change-in-update");var option_styles_default=i`
  :host {
    --current-text-color: var(--wa-color-brand-on-loud);

    display: block;
    color: var(--wa-color-text-normal);
    -webkit-user-select: none;
    user-select: none;

    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    padding: 0.5em 1em 0.5em 0.25em;
    border-radius: var(--wa-border-radius-s);
    line-height: var(--wa-line-height-condensed);
    transition: var(--wa-transition-fast) background-color var(--wa-transition-easing);
    cursor: pointer;
  }

  :host(:focus) {
    outline: none;
  }

  @media (hover: hover) {
    :host(:not(:state(disabled), :state(current)):is(:state(hover), :hover)) {
      background-color: var(--wa-color-neutral-fill-normal);
      color: var(--wa-color-neutral-on-normal);
    }
  }

  :host(:state(current)),
  :host(:state(disabled):state(current)) {
    background-color: var(--wa-form-control-activated-color);
    color: var(--current-text-color);
    opacity: 1;
  }

  :host(:state(disabled)) {
    outline: none;
    opacity: 0.5;
    cursor: not-allowed;
  }

  .label {
    flex: 1 1 auto;
    display: inline-block;
  }

  .check {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--wa-font-size-smaller);
    visibility: hidden;
    width: 2em;
  }

  :host(:state(selected)) .check {
    visibility: visible;
  }

  .start,
  .end {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
  }

  .start::slotted(*) {
    margin-inline-end: 0.5em;
  }

  .end::slotted(*) {
    margin-inline-start: 0.5em;
  }

  @media (forced-colors: active) {
    :host(:hover:not([aria-disabled='true'])) {
      outline: dashed 1px SelectedItem;
      outline-offset: -1px;
    }
  }
`;function getText(root,depth=0){if(!root||!globalThis.Node)return"";if(typeof root[Symbol.iterator]=="function")return(Array.isArray(root)?root:[...root]).map(node2=>getText(node2,--depth)).join("");let node=root;if(node.nodeType===Node.TEXT_NODE)return node.textContent??"";if(node.nodeType===Node.ELEMENT_NODE){let element=node;if(element.hasAttribute("slot")||element.matches("style, script"))return"";if(element instanceof HTMLSlotElement){let assignedNodes=element.assignedNodes({flatten:!0});if(assignedNodes.length>0)return getText(assignedNodes,--depth)}return depth>-1?getText(element,--depth):element.textContent??""}return node.hasChildNodes()?getText(node.childNodes,--depth):""}var WaOption=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.cachedDefaultLabel="",this.isInitialized=!1,this.isDefaultLabelDirty=!0,this.current=!1,this.value="",this.disabled=!1,this.selected=!1,this.defaultSelected=!1,this._label="",this.handleHover=event=>{event.type==="mouseenter"?this.customStates.set("hover",!0):event.type==="mouseleave"&&this.customStates.set("hover",!1)}}set label(value){let oldValue=this._label;this._label=value||"",this._label!==oldValue&&this.requestUpdate("label",oldValue)}get label(){return this._label?this._label:this.defaultLabel}get defaultLabel(){return(this.isDefaultLabelDirty||!this.cachedDefaultLabel)&&this.updateDefaultLabel(),this.cachedDefaultLabel}connectedCallback(){super.connectedCallback(),this.setAttribute("role","option"),this.setAttribute("aria-selected","false"),this.addEventListener("mouseenter",this.handleHover),this.addEventListener("mouseleave",this.handleHover)}disconnectedCallback(){super.disconnectedCallback(),this.removeEventListener("mouseenter",this.handleHover),this.removeEventListener("mouseleave",this.handleHover)}handleDefaultSlotChange(){if(this.isDefaultLabelDirty=!0,!this.isInitialized){this.isInitialized=!0;return}let controller=this.closest("wa-select, wa-combobox");controller&&customElements.whenDefined(controller.localName).then(()=>controller.handleDefaultSlotChange?.())}willUpdate(changedProperties){changedProperties.has("defaultSelected")&&(this.didSSR&&this.hasUpdated||!this.didSSR)&&this.syncDefaultSelected(),super.willUpdate(changedProperties)}syncDefaultSelected(){if("closest"in this&&!this.closest("wa-combobox, wa-select")?.hasInteracted&&this.defaultSelected){let oldVal=this.selected;this.selected=this.defaultSelected,this.requestUpdate("selected",oldVal)}}updated(changedProperties){changedProperties.has("disabled")&&(this.setAttribute("aria-disabled",this.disabled?"true":"false"),this.customStates.set("disabled",this.disabled)),changedProperties.has("selected")&&(this.setAttribute("aria-selected",this.selected?"true":"false"),this.customStates.set("selected",this.selected)),changedProperties.has("value")&&(typeof this.value!="string"&&(this.value=String(this.value)),this.handleDefaultSlotChange()),changedProperties.has("current")&&this.customStates.set("current",this.current),super.updated(changedProperties)}async firstUpdated(changedProperties){if(super.firstUpdated(changedProperties),this.didSSR&&!this.hasUpdated?(await this.updateComplete,this.syncDefaultSelected()):this.syncDefaultSelected(),this.selected&&!this.defaultSelected){let parent=this.closest("wa-select, wa-combobox");parent&&!parent.hasInteracted&&(await customElements.whenDefined(parent?.localName),await parent.updateComplete,parent.selectionChanged?.())}}updateDefaultLabel(){let oldValue=this.cachedDefaultLabel;this.cachedDefaultLabel=getText(this).trim(),this.isDefaultLabelDirty=!1;let changed=this.cachedDefaultLabel!==oldValue;return!this._label&&changed&&this.requestUpdate("label",oldValue),changed}render(){let selected=this.selected;return this.didSSR&&!this.hasUpdated?(this.updateComplete.then(()=>{this.requestUpdate()}),A):b2`
      ${selected?b2`<wa-icon
            part="checked-icon"
            class="check"
            name="check"
            library="system"
            variant="solid"
            aria-hidden="true"
          ></wa-icon>`:b2`<span part="checked-icon" class="check" aria-hidden="true"></span>`}
      <slot part="start" name="start" class="start"></slot>
      <slot part="label" class="label" @slotchange=${this.handleDefaultSlotChange}></slot>
      <slot part="end" name="end" class="end"></slot>
    `}};WaOption.css=option_styles_default;__decorateClass([e5(".label")],WaOption.prototype,"defaultSlot",2);__decorateClass([r5()],WaOption.prototype,"current",2);__decorateClass([n4({reflect:!0})],WaOption.prototype,"value",2);__decorateClass([n4({type:Boolean})],WaOption.prototype,"disabled",2);__decorateClass([n4({type:Boolean,attribute:!1})],WaOption.prototype,"selected",2);__decorateClass([n4({type:Boolean,attribute:"selected"})],WaOption.prototype,"defaultSelected",2);__decorateClass([n4()],WaOption.prototype,"label",1);WaOption=__decorateClass([t3("wa-option")],WaOption);var radio_styles_default=i`
  :host {
    --checked-icon-color: var(--wa-form-control-activated-color);
    --checked-icon-scale: 0.7;

    color: var(--wa-form-control-value-color);
    display: inline-flex;
    flex-direction: row;
    align-items: top;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    cursor: pointer;
    user-select: none;
    -webkit-user-select: none;
  }

  :host(:focus) {
    outline: none;
  }

  /* When the control isn't checked, hide the circle for Windows High Contrast mode a11y */
  :host(:not(:state(checked))) svg circle {
    opacity: 0;
  }

  [part~='label'] {
    display: inline;
  }

  [part~='hint'] {
    margin-block-start: 0.5em;
  }

  /* Default spacing for default appearance radios */
  :host([appearance='default']) {
    margin-block: 0.375em; /* Half of the original 0.75em gap on each side */
  }

  :host([appearance='default'][data-wa-radio-horizontal]) {
    margin-block: 0;
    margin-inline: 0.5em; /* Half of the original 1em gap on each side */
  }

  /* Remove margin from first/last items to prevent extra space */
  :host([appearance='default'][data-wa-radio-first]) {
    margin-block-start: 0;
    margin-inline-start: 0;
  }

  :host([appearance='default'][data-wa-radio-last]) {
    margin-block-end: 0;
    margin-inline-end: 0;
  }

  /* Button appearance have no spacing, they get handled by the overlap margins below */
  :host([appearance='button']) {
    margin: 0;
    align-items: center;
    min-height: var(--wa-form-control-height);
    background-color: var(--wa-color-surface-default);
    border: var(--wa-form-control-border-width) var(--wa-form-control-border-style) var(--wa-form-control-border-color);
    border-radius: var(--wa-border-radius-m);
    padding: 0 var(--wa-form-control-padding-inline);
    transition:
      background-color var(--wa-transition-fast),
      border-color var(--wa-transition-fast);
  }

  /* Default appearance */
  :host([appearance='default']) {
    .control {
      flex: 0 0 auto;
      position: relative;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      border-color: var(--wa-form-control-border-color);
      border-radius: 50%;
      border-style: var(--wa-form-control-border-style);
      border-width: var(--wa-form-control-border-width);
      background-color: var(--wa-form-control-background-color);
      color: transparent;
      transition:
        background var(--wa-transition-normal),
        border-color var(--wa-transition-fast),
        box-shadow var(--wa-transition-fast),
        color var(--wa-transition-fast);
      transition-timing-function: var(--wa-transition-easing);

      margin-inline-end: 0.5em;
    }

    .checked-icon {
      display: flex;
      fill: currentColor;
      width: var(--wa-form-control-toggle-size);
      height: var(--wa-form-control-toggle-size);
      scale: var(--checked-icon-scale);
    }
  }

  /* Button appearance */
  :host([appearance='button']) {
    .control {
      display: none;
    }
  }

  /* Checked */
  :host(:state(checked)) .control {
    color: var(--checked-icon-color);
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-form-control-background-color);
  }

  /* Focus */
  :host(:focus-visible) .control {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Disabled */
  :host(:state(disabled)) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Horizontal grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-first]) {
    border-start-end-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-horizontal][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-end-start-radius: 0;
  }

  /* Vertical grouping - remove inner border radius */
  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-inner]) {
    border-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-first]) {
    border-end-start-radius: 0;
    border-end-end-radius: 0;
  }

  :host([appearance='button'][data-wa-radio-vertical][data-wa-radio-last]) {
    border-start-start-radius: 0;
    border-start-end-radius: 0;
  }

  @media (hover: hover) {
    :host([appearance='button']:hover:not(:state(disabled), :state(checked))) {
      background-color: color-mix(in srgb, var(--wa-color-surface-default) 95%, var(--wa-color-mix-hover));
    }
  }

  :host([appearance='button']:focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  :host([appearance='button']:state(checked)) {
    border-color: var(--wa-form-control-activated-color);
    background-color: var(--wa-color-brand-fill-quiet);
  }

  :host([appearance='button']:state(checked):focus-visible) {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Button overlap margins */
  :host([appearance='button'][data-wa-radio-horizontal]:not([data-wa-radio-first])) {
    margin-inline-start: calc(-1 * var(--wa-form-control-border-width));
  }

  :host([appearance='button'][data-wa-radio-vertical]:not([data-wa-radio-first])) {
    margin-block-start: calc(-1 * var(--wa-form-control-border-width));
  }

  /* Ensure interactive states are visible above adjacent buttons */
  :host([appearance='button']:hover),
  :host([appearance='button']:state(checked)) {
    position: relative;
    z-index: 1;
  }

  :host([appearance='button']:focus-visible) {
    z-index: 2;
  }
`;var WaRadio=class extends WebAwesomeFormAssociatedElement{constructor(){super(),this.checked=!1,this.forceDisabled=!1,this.appearance="default",this.disabled=!1,this.handleClick=()=>{!this.disabled&&!this.forceDisabled&&(this.checked=!0)},this.addEventListener("click",this.handleClick)}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.setInitialAttributes()}setInitialAttributes(){this.setAttribute("role","radio"),this.tabIndex=0,this.setAttribute("aria-disabled",this.disabled||this.forceDisabled?"true":"false")}updated(changedProperties){if(super.updated(changedProperties),changedProperties.has("checked")&&(this.customStates.set("checked",this.checked),this.setAttribute("aria-checked",this.checked?"true":"false"),!this.disabled&&!this.forceDisabled&&(this.tabIndex=this.checked?0:-1)),changedProperties.has("disabled")||changedProperties.has("forceDisabled")){let effectivelyDisabled=this.disabled||this.forceDisabled;this.customStates.set("disabled",effectivelyDisabled),this.setAttribute("aria-disabled",effectivelyDisabled?"true":"false"),effectivelyDisabled?this.tabIndex=-1:this.tabIndex=this.checked?0:-1}}setValue(){}render(){return b2`
      <span part="control" class="control">
        ${this.checked?b2`
              <svg viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg" part="checked-icon" class="checked-icon">
                <circle cx="8" cy="8" r="8" />
              </svg>
            `:""}
      </span>

      <slot part="label" class="label"></slot>
    `}};WaRadio.css=[form_control_styles_default,size_styles_default,radio_styles_default];__decorateClass([r5()],WaRadio.prototype,"checked",2);__decorateClass([r5()],WaRadio.prototype,"forceDisabled",2);__decorateClass([n4({reflect:!0})],WaRadio.prototype,"value",2);__decorateClass([n4({reflect:!0})],WaRadio.prototype,"appearance",2);__decorateClass([n4({reflect:!0})],WaRadio.prototype,"size",2);__decorateClass([watch("size")],WaRadio.prototype,"handleSizeChange",1);__decorateClass([n4({type:Boolean})],WaRadio.prototype,"disabled",2);WaRadio=__decorateClass([t3("wa-radio")],WaRadio);WaRadio.disableWarning?.("change-in-update");var radio_group_styles_default=i`
  .form-control {
    position: relative;
    border: none;
    padding: 0;
    margin: 0;
  }

  .label {
    padding: 0;
  }

  .radio-group-required .label::after {
    content: var(--wa-form-control-required-content);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  [part~='form-control-input'] {
    display: flex;
    flex-direction: column;
    flex-wrap: wrap;
    gap: 0; /* Radios handle their own spacing */
  }

  /* Horizontal */
  :host([orientation='horizontal']) [part~='form-control-input'] {
    flex-direction: row;
  }

  /* Help text */
  [part~='hint'] {
    margin-block-start: 0.5em;
  }
`;var urlAlphabet="useandom-26T198340PX75pxJACKVERYMINDBUSHWOLF_GQZbfghjklqvwyzrict";var nanoid=(size3=21)=>{let id3="",bytes=crypto.getRandomValues(new Uint8Array(size3|=0));for(;size3--;)id3+=urlAlphabet[bytes[size3]&63];return id3};function uniqueId(prefix=""){return`${prefix}${nanoid()}`}var WaRadioGroup=class extends WebAwesomeFormAssociatedElement{constructor(){super(),this.hasSlotController=new HasSlotController(this,"hint","label"),this.label="",this.hint="",this.name=null,this.disabled=!1,this.orientation="vertical",this._value=null,this.defaultValue=this.getAttribute("value")||null,this.required=!1,this.withLabel=!1,this.withHint=!1,this.handleRadioClick=e10=>{let clickedRadio=e10.target.closest("wa-radio");if(!clickedRadio||clickedRadio.disabled||clickedRadio.forceDisabled||this.disabled)return;let oldValue=this.value;this.value=clickedRadio.value,clickedRadio.checked=!0;let radios=this.getAllRadios();for(let radio of radios)clickedRadio!==radio&&(radio.checked=!1,radio.setAttribute("tabindex","-1"));this.value!==oldValue&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})},this.addEventListener("keydown",this.handleKeyDown),this.addEventListener("click",this.handleRadioClick)}static get validators(){let validators=[RequiredValidator({validationElement:Object.assign(document.createElement("input"),{required:!0,type:"radio",name:uniqueId("__wa-radio")})})];return[...super.validators,...validators]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(val){typeof val=="number"&&(val=String(val)),this.valueHasChanged=!0,this._value=val}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}get validationTarget(){if(!1)return;let radio=this.querySelector(":is(wa-radio):not([disabled])");if(radio)return radio}updated(changedProperties){(changedProperties.has("disabled")||changedProperties.has("size")||changedProperties.has("value")||changedProperties.has("defaultValue"))&&this.syncRadioElements()}formResetCallback(...args){this._value=null,super.formResetCallback(...args),this.syncRadioElements()}getAllRadios(){return[...this.querySelectorAll("wa-radio")]}handleLabelClick(){this.focus()}async syncRadioElements(){let radios=this.getAllRadios();if(radios.forEach((radio,index)=>{this.size&&radio.setAttribute("size",this.size),radio.toggleAttribute("data-wa-radio-horizontal",this.orientation!=="vertical"),radio.toggleAttribute("data-wa-radio-vertical",this.orientation==="vertical"),radio.toggleAttribute("data-wa-radio-first",index===0),radio.toggleAttribute("data-wa-radio-inner",index!==0&&index!==radios.length-1),radio.toggleAttribute("data-wa-radio-last",index===radios.length-1),radio.forceDisabled=this.disabled}),await Promise.all(radios.map(async radio=>{await radio.updateComplete,!radio.disabled&&radio.value===this.value?radio.checked=!0:radio.checked=!1})),this.disabled)radios.forEach(radio=>{radio.tabIndex=-1});else{let enabledRadios=radios.filter(radio=>!radio.disabled),checkedRadio=enabledRadios.find(radio=>radio.checked);enabledRadios.length>0&&(checkedRadio?enabledRadios.forEach(radio=>{radio.tabIndex=radio.checked?0:-1}):enabledRadios.forEach((radio,index)=>{radio.tabIndex=index===0?0:-1})),radios.filter(radio=>radio.disabled).forEach(radio=>{radio.tabIndex=-1})}}handleKeyDown(event){if(!["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"," "].includes(event.key)||this.disabled)return;let radios=this.getAllRadios().filter(radio=>!radio.disabled);if(radios.length<=0)return;event.preventDefault();let oldValue=this.value,checkedRadio=radios.find(radio=>radio.checked)??radios[0],incr=event.key===" "?0:["ArrowUp","ArrowLeft"].includes(event.key)?-1:1,index=radios.indexOf(checkedRadio)+incr;index||(index=0),index<0&&(index=radios.length-1),index>radios.length-1&&(index=0);let hasRadioButtons=radios.some(radio=>radio.tagName.toLowerCase()==="wa-radio-button");this.getAllRadios().forEach(radio=>{radio.checked=!1,hasRadioButtons||radio.setAttribute("tabindex","-1")}),this.value=radios[index].value,radios[index].checked=!0,hasRadioButtons?radios[index].shadowRoot.querySelector("button").focus():(radios[index].setAttribute("tabindex","0"),radios[index].focus()),this.value!==oldValue&&this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),event.preventDefault()}focus(options){if(this.disabled)return;let radios=this.getAllRadios(),checked=radios.find(radio=>radio.checked),firstEnabledRadio=radios.find(radio=>!radio.disabled),radioToFocus=checked||firstEnabledRadio;radioToFocus&&radioToFocus.focus(options)}render(){let hasLabelSlot=this.hasSlotController.test("label","withLabel"),hasHintSlot=this.hasSlotController.test("hint","withHint"),hasLabel=this.label?!0:!!hasLabelSlot,hasHint=this.hint?!0:!!hasHintSlot;return b2`
      <fieldset
        part="form-control"
        class=${e7({"form-control":!0,"form-control-radio-group":!0,"form-control-has-label":hasLabel})}
        role="radiogroup"
        aria-labelledby="label"
        aria-describedby="hint"
        aria-errormessage="error-message"
        aria-orientation=${this.orientation}
      >
        <label
          part="form-control-label"
          id="label"
          class=${e7({label:!0,"has-label":hasLabel})}
          aria-hidden=${hasLabel?"false":"true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <slot part="form-control-input" @slotchange=${this.syncRadioElements}></slot>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${e7({"has-slotted":hasHint})}
          aria-hidden=${hasHint?"false":"true"}
          >${this.hint}</slot
        >
      </fieldset>
    `}};WaRadioGroup.css=[size_styles_default,form_control_styles_default,radio_group_styles_default];WaRadioGroup.shadowRootOptions={...WebAwesomeFormAssociatedElement.shadowRootOptions,delegatesFocus:!0};__decorateClass([e5("slot:not([name])")],WaRadioGroup.prototype,"defaultSlot",2);__decorateClass([n4()],WaRadioGroup.prototype,"label",2);__decorateClass([n4({attribute:"hint"})],WaRadioGroup.prototype,"hint",2);__decorateClass([n4({reflect:!0})],WaRadioGroup.prototype,"name",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaRadioGroup.prototype,"disabled",2);__decorateClass([n4({reflect:!0})],WaRadioGroup.prototype,"orientation",2);__decorateClass([r5()],WaRadioGroup.prototype,"value",1);__decorateClass([n4({attribute:"value",reflect:!0})],WaRadioGroup.prototype,"defaultValue",2);__decorateClass([n4({reflect:!0})],WaRadioGroup.prototype,"size",2);__decorateClass([watch("size")],WaRadioGroup.prototype,"handleSizeChange",1);__decorateClass([n4({type:Boolean,reflect:!0})],WaRadioGroup.prototype,"required",2);__decorateClass([n4({type:Boolean,attribute:"with-label"})],WaRadioGroup.prototype,"withLabel",2);__decorateClass([n4({type:Boolean,attribute:"with-hint"})],WaRadioGroup.prototype,"withHint",2);WaRadioGroup=__decorateClass([t3("wa-radio-group")],WaRadioGroup);WaRadioGroup.disableWarning?.("change-in-update");var select_styles_default=i`
  :host {
    --tag-max-size: 10ch;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);
  }

  /* Add ellipses to multi select options */
  :host wa-tag::part(content) {
    display: initial;
    white-space: nowrap;
    text-overflow: ellipsis;
    overflow: hidden;
    max-width: var(--tag-max-size);
  }

  :host .disabled [part~='combobox'] {
    opacity: 0.5;
    cursor: not-allowed;
    outline: none;
  }

  :host .enabled:is(.open, :focus-within) [part~='combobox'] {
    outline-color: var(--wa-color-focus);
  }

  /** The popup */
  .select {
    flex: 1 1 auto;
    display: inline-flex;
    width: 100%;
    position: relative;
    vertical-align: middle;

    /* Pass through from select to the popup */
    --show-duration: inherit;
    --hide-duration: inherit;

    &::part(popup) {
      z-index: 900;
    }

    &[data-current-placement^='top']::part(popup) {
      transform-origin: bottom;
    }

    &[data-current-placement^='bottom']::part(popup) {
      transform-origin: top;
    }
  }

  /* Combobox */
  .combobox {
    flex: 1;
    display: flex;
    width: 100%;
    min-width: 0;
    align-items: center;
    justify-content: start;

    min-height: var(--wa-form-control-height);

    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    color: var(--wa-form-control-value-color);
    cursor: pointer;
    font-family: inherit;
    font-weight: var(--wa-form-control-value-font-weight);
    line-height: var(--wa-form-control-value-line-height);
    overflow: hidden;
    padding: 0 var(--wa-form-control-padding-inline);
    position: relative;
    vertical-align: middle;
    transition:
      background-color var(--wa-transition-normal),
      border-color var(--wa-transition-normal),
      outline-color var(--wa-transition-fast);
    transition-timing-function: var(--wa-transition-easing);
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    /* Pills */
    :host([pill]) & {
      border-radius: var(--wa-border-radius-pill);
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .combobox {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .combobox {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  .display-input {
    position: relative;
    width: 100%;
    font: inherit;
    border: none;
    background: none;
    line-height: var(--wa-form-control-value-line-height);
    color: var(--wa-form-control-value-color);
    cursor: inherit;
    overflow: hidden;
    padding: 0;
    margin: 0;
    -webkit-appearance: none;

    &:focus {
      outline: none;
    }

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
    }
  }

  /* Manage spacing when tags are present */
  :host([multiple]) {
    --_padding-with-tags: calc(var(--wa-form-control-height) * 0.1 - var(--wa-form-control-border-width));

    & .combobox:has(.tags wa-tag) {
      padding-block: var(--_padding-with-tags);
      padding-inline-start: var(--_padding-with-tags);
    }
  }

  /* Visually hide the display input when multiple is enabled */
  :host([multiple]) .combobox:has(.tags wa-tag) .display-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
  }

  .value-input {
    position: absolute;
    z-index: -1;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    opacity: 0;
    padding: 0;
    margin: 0;
  }

  .tags {
    display: flex;
    flex: 1;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.25em;

    /* Nested inside the box, so a step down from the box's radius */
    & wa-tag:not([pill]) {
      border-radius: var(--wa-border-radius-s);
    }

    .disabled & {
      cursor: not-allowed !important;
    }
  }

  /* Start and End */

  .start,
  .end {
    flex: 0;
    display: inline-flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
  }

  .end::slotted(*) {
    margin-inline-start: var(--wa-form-control-padding-inline);
  }

  .start::slotted(*) {
    margin-inline-end: var(--wa-form-control-padding-inline);
  }

  :host([multiple]) .combobox:has(.tags wa-tag) .start::slotted(*) {
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - var(--_padding-with-tags));
  }

  /* Clear button */
  [part~='clear-button'] {
    flex: 0 0 auto;
    display: inline-flex;
    align-self: stretch;
    align-items: center;
    justify-content: center;
    inline-size: 1.5em;
    font-size: inherit;
    color: var(--wa-color-neutral-on-quiet);
    border: none;
    background: none;
    padding: 0;
    transition: color var(--wa-transition-normal);
    cursor: pointer;
    /* The box is wider than the glyph, so overhang half that growth on each side. Keeps the glyph
       on the same trailing axis as the segmented-field pickers' clear buttons. */
    margin-inline-start: calc(var(--wa-form-control-padding-inline) - 0.125em);
    margin-inline-end: -0.125em;

    &:focus {
      outline: none;
    }

    @media (hover: hover) {
      &:hover {
        color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
      }
    }

    &:active {
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
    }
  }

  /* Expand icon */
  .expand-icon {
    flex: 0 0 auto;
    display: flex;
    align-items: center;
    color: var(--wa-color-neutral-on-quiet);
    transition: rotate var(--wa-transition-slow) var(--wa-transition-easing);
    rotate: 0deg;
    margin-inline-start: var(--wa-form-control-padding-inline);

    .open & {
      rotate: -180deg;
    }
  }

  /* Listbox */
  .listbox {
    display: block;
    position: relative;
    font: inherit;
    box-shadow: var(--wa-shadow-m);
    background: var(--wa-color-surface-raised);
    border-color: var(--wa-color-surface-border);
    border-radius: var(--wa-border-radius-m);
    border-style: var(--wa-border-style);
    border-width: var(--wa-border-width-s);
    padding: 0.25em;
    overflow: auto;
    overscroll-behavior: none;

    /* Make sure it adheres to the popup's auto size */
    max-width: var(--auto-size-available-width);
    max-height: var(--auto-size-available-height);

    &::slotted(wa-divider) {
      --spacing: 0.5em;
    }
  }

  /* Space options with half the listbox's padding */
  .listbox slot:not([name]) {
    display: flex;
    flex-direction: column;
    gap: 0.125em;
  }

  slot:not([name])::slotted(small) {
    display: block;
    font-size: var(--wa-font-size-smaller);
    font-weight: var(--wa-font-weight-semibold);
    color: var(--wa-color-text-quiet);
    padding-block: 0.5em;
    padding-inline: 2.25em;
  }
`;var e8=class extends i5{constructor(i8){if(super(i8),this.it=A,i8.type!==t4.CHILD)throw Error(this.constructor.directiveName+"() can only be used in child bindings")}render(r8){if(r8===A||r8==null)return this._t=void 0,this.it=r8;if(r8===E)return r8;if(typeof r8!="string")throw Error(this.constructor.directiveName+"() called with a non-string value");if(r8===this.it)return this._t;this.it=r8;let s4=[r8];return s4.raw=s4,this._t={_$litType$:this.constructor.resultType,strings:s4,values:[]}}};e8.directiveName="unsafeHTML",e8.resultType=1;var o9=e6(e8);var WaSelect=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.cachedOptions=null,this.hasSlotController=new HasSlotController(this,"hint","label"),this.localize=new LocalizeController2(this),this.selectionOrder=new Map,this.typeToSelectString="",this.slotChangePending=!1,this.displayLabel="",this.selectedOptions=[],this.name="",this._defaultValue=null,this.size="m",this.placeholder="",this.multiple=!1,this.maxOptionsVisible=3,this.disabled=!1,this.withClear=!1,this.open=!1,this.appearance="outlined",this.pill=!1,this.label="",this.placement="bottom",this.hint="",this.withLabel=!1,this.withHint=!1,this.required=!1,this.getTag=option=>b2`
        <wa-tag
          part="tag"
          exportparts="
            base:tag__base,
            content:tag__content,
            remove-button:tag__remove-button,
            remove-button__base:tag__remove-button__base
          "
          ?pill=${this.pill}
          size=${this.size}
          with-remove
          data-value=${option.value}
          @wa-remove=${event=>this.handleTagRemove(event,option)}
        >
          ${option.label}
        </wa-tag>
      `,this.handleDocumentFocusIn=event=>{let path=event.composedPath();this&&!path.includes(this)&&this.hide()},this.handleDocumentKeyDown=event=>{let target=event.target,isClearButton=target.closest('[part~="clear-button"]')!==null,isButton=target.closest("wa-button")!==null;if(!(isClearButton||isButton)){if(event.key==="Escape"&&this.open&&isTopDismissible(this)&&(event.preventDefault(),event.stopPropagation(),this.hide(),this.displayInput.focus({preventScroll:!0})),event.key==="Enter"||event.key===" "&&this.typeToSelectString===""){if(event.preventDefault(),event.stopImmediatePropagation(),!this.open){this.show();return}this.currentOption&&!this.currentOption.disabled&&(this.valueHasChanged=!0,this.hasInteracted=!0,this.multiple?this.toggleOptionSelection(this.currentOption):this.setSelectedOptions(this.currentOption),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.multiple||(this.hide(),this.displayInput.focus({preventScroll:!0})));return}if(["ArrowUp","ArrowDown","Home","End"].includes(event.key)){let allOptions=this.getAllOptions(),currentIndex=allOptions.indexOf(this.currentOption),newIndex=Math.max(0,currentIndex);if(event.preventDefault(),!this.open&&(this.show(),this.currentOption))return;event.key==="ArrowDown"?(newIndex=currentIndex+1,newIndex>allOptions.length-1&&(newIndex=0)):event.key==="ArrowUp"?(newIndex=currentIndex-1,newIndex<0&&(newIndex=allOptions.length-1)):event.key==="Home"?newIndex=0:event.key==="End"&&(newIndex=allOptions.length-1),this.setCurrentOption(allOptions[newIndex])}if(event.key?.length===1||event.key==="Backspace"){let allOptions=this.getAllOptions();if(event.metaKey||event.ctrlKey||event.altKey)return;if(!this.open){if(event.key==="Backspace")return;this.show()}event.stopPropagation(),event.preventDefault(),clearTimeout(this.typeToSelectTimeout),this.typeToSelectTimeout=window.setTimeout(()=>this.typeToSelectString="",1e3),event.key==="Backspace"?this.typeToSelectString=this.typeToSelectString.slice(0,-1):this.typeToSelectString+=event.key.toLowerCase();for(let option of allOptions)if(option.label.toLowerCase().startsWith(this.typeToSelectString)){this.setCurrentOption(option);break}}}},this.handleDocumentMouseDown=event=>{let path=event.composedPath();this&&!path.includes(this)&&this.hide()}}static get validators(){let validators=[RequiredValidator({validationElement:Object.assign(document.createElement("select"),{required:!0})})];return[...super.validators,...validators]}get validationTarget(){return this.valueInput}set defaultValue(val){this._defaultValue=this.convertDefaultValue(val)}get defaultValue(){return this.convertDefaultValue(this._defaultValue)}rawValuesEqual(a4,b3){return a4==null&&b3==null?!0:a4==null||b3==null||a4.length!==b3.length?!1:a4.every((v2,i8)=>v2===b3[i8])}convertDefaultValue(val){return!(this.multiple||this.hasAttribute("multiple"))&&Array.isArray(val)&&(val=val[0]),val}set value(val){let oldValue=this.value;val instanceof FormData&&(val=val.getAll(this.name)),val!=null&&!Array.isArray(val)&&(val=[val]);let oldRawValue=this._value;this._value=val??null,this.rawValuesEqual(oldRawValue,this._value)||(this.valueHasChanged=!0,this.requestUpdate("value",oldValue))}get value(){let value=this._value??this.defaultValue??null;value!=null&&(value=Array.isArray(value)?value:[value]),this.optionValues=new Set(this.getAllOptions().filter(option=>!option.disabled).map(option=>option.value));let ret=value;return value!=null&&(ret=value.filter(v2=>this.optionValues.has(v2)),ret=this.multiple?ret:ret[0],ret=ret??null),ret}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.processSlotChange(),this.open=!1}disconnectedCallback(){super.disconnectedCallback(),this.removeOpenListeners(),this.cachedOptions=null}updateDefaultValue(){let defaultSelectedOptions=this.getAllOptions().filter(el=>el.hasAttribute("selected")||el.defaultSelected);if(defaultSelectedOptions.length>0){let selectedValues=defaultSelectedOptions.map(el=>el.value);this._defaultValue=this.multiple?selectedValues:selectedValues[0]}this.hasAttribute("value")&&(this._defaultValue=this.getAttribute("value")||null)}addOpenListeners(){document.addEventListener("focusin",this.handleDocumentFocusIn),document.addEventListener("keydown",this.handleDocumentKeyDown),document.addEventListener("mousedown",this.handleDocumentMouseDown),registerDismissible(this),this.getRootNode()!==document&&this.getRootNode().addEventListener("focusin",this.handleDocumentFocusIn)}removeOpenListeners(){document.removeEventListener("focusin",this.handleDocumentFocusIn),document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("mousedown",this.handleDocumentMouseDown),unregisterDismissible(this),this.getRootNode()!==document&&this.getRootNode().removeEventListener("focusin",this.handleDocumentFocusIn)}handleFocus(){this.displayInput.setSelectionRange(0,0)}handleLabelClick(){this.displayInput.focus()}handleComboboxClick(event){event.preventDefault()}handleComboboxMouseDown(event){let isButton=event.composedPath().some(el=>el instanceof Element&&el.tagName.toLowerCase()==="wa-button");this.disabled||isButton||(event.preventDefault(),this.displayInput.focus({preventScroll:!0}),this.open=!this.open)}handleComboboxKeyDown(event){event.stopPropagation(),this.handleDocumentKeyDown(event)}handleClearClick(event){event.stopPropagation(),this.hasInteracted=!0,this.valueHasChanged=!0,this.value!==null&&(this.displayLabel="",this.selectionOrder.clear(),this.setSelectedOptions([]),this.displayInput.focus({preventScroll:!0}),this.updateComplete.then(()=>{this.dispatchEvent(new WaClearEvent),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))}handleClearMouseDown(event){event.stopPropagation(),event.preventDefault()}handleOptionClick(event){let option=event.target.closest("wa-option");option&&!option.disabled&&(this.hasInteracted=!0,this.valueHasChanged=!0,this.multiple?this.toggleOptionSelection(option):this.setSelectedOptions(option),this.updateComplete.then(()=>this.displayInput.focus({preventScroll:!0})),this.requestUpdate("value"),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}),this.multiple||(this.hide(),this.displayInput.focus({preventScroll:!0})))}handleDefaultSlotChange(){this.slotChangePending||(this.slotChangePending=!0,queueMicrotask(()=>{this.slotChangePending=!1,this.processSlotChange()}))}processSlotChange(){if(customElements.get("wa-option")||customElements.whenDefined("wa-option").then(()=>this.handleDefaultSlotChange()),this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleDefaultSlotChange()});return}this.cachedOptions=null;let allOptions=this.getAllOptions();this.updateDefaultValue();let value=this.value;if(value==null||!this.valueHasChanged&&!this.hasInteracted){this.selectionChanged();return}Array.isArray(value)||(value=[value]);let selectedOptions=allOptions.filter(el=>value.includes(el.value));this.setSelectedOptions(selectedOptions)}handleTagRemove(event,directOption){if(event.stopPropagation(),this.disabled)return;this.hasInteracted=!0,this.valueHasChanged=!0;let option=directOption;if(!option){let tagElement=event.target.closest("wa-tag[data-value]");if(tagElement){let value=tagElement.dataset.value;option=this.selectedOptions.find(opt=>opt.value===value)}}option&&(this.toggleOptionSelection(option,!1),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))}))}getAllOptions(){return this.cachedOptions?this.cachedOptions:this?.querySelectorAll?(this.cachedOptions=[...this.querySelectorAll("wa-option")],this.cachedOptions):[]}getFirstOption(){return this.querySelector("wa-option")}setCurrentOption(option){this.getAllOptions().forEach(el=>{el.current=!1,el.tabIndex=-1}),option&&(this.currentOption=option,option.current=!0,option.tabIndex=0,option.focus({preventScroll:!0}),this.open&&!this.listbox.hidden&&scrollIntoView(option,this.listbox,"vertical","auto"))}setSelectedOptions(option){let allOptions=this.getAllOptions(),newSelectedOptions=Array.isArray(option)?option:[option];allOptions.forEach(el=>{newSelectedOptions.includes(el)||(el.selected=!1)}),newSelectedOptions.length&&newSelectedOptions.forEach(el=>el.selected=!0),this.selectionChanged()}toggleOptionSelection(option,force){force===!0||force===!1?option.selected=force:option.selected=!option.selected,this.selectionChanged()}selectionChanged(){let newSelectedOptions=this.getAllOptions().filter(el=>{if(!this.hasInteracted&&!this.valueHasChanged){let defaultValue=this.defaultValue,defaultValues=Array.isArray(defaultValue)?defaultValue:[defaultValue];return el.hasAttribute("selected")||el.defaultSelected||el.selected||defaultValues?.includes(el.value)}return el.selected}),newSelectedValues=new Set(newSelectedOptions.map(el=>el.value));for(let value of this.selectionOrder.keys())newSelectedValues.has(value)||this.selectionOrder.delete(value);let nextOrder=(this.selectionOrder.size>0?Math.max(...this.selectionOrder.values()):-1)+1;for(let option of newSelectedOptions)this.selectionOrder.has(option.value)||this.selectionOrder.set(option.value,nextOrder++);this.selectedOptions=newSelectedOptions.sort((a4,b3)=>{let orderA=this.selectionOrder.get(a4.value)??0,orderB=this.selectionOrder.get(b3.value)??0;return orderA-orderB});let selectedValues=new Set(this.selectedOptions.map(el=>el.value));if(selectedValues.size>0||this._value){let oldValue=this._value;if(this._value==null){let value=this.defaultValue??[];this._value=Array.isArray(value)?value:[value]}this._value=this._value?.filter(value=>!this.optionValues?.has(value))??null,this._value?.unshift(...selectedValues),this.requestUpdate("value",oldValue)}if(this.multiple)this.placeholder&&!this.value?.length?this.displayLabel="":this.displayLabel=this.localize.term("numOptionsSelected",this.selectedOptions.length);else{let selectedOption=this.selectedOptions[0];this.displayLabel=selectedOption?.label??""}this.updateComplete.then(()=>{this.updateValidity()})}get tags(){return this.selectedOptions.map((option,index)=>{if(index<this.maxOptionsVisible||this.maxOptionsVisible<=0){let tag=this.getTag(option,index);return tag?typeof tag=="string"?o9(tag):tag:null}else if(index===this.maxOptionsVisible)return b2`
          <wa-tag
            part="tag"
            exportparts="
              base:tag__base,
              content:tag__content,
              remove-button:tag__remove-button,
              remove-button__base:tag__remove-button__base
            "
            ?pill=${this.pill}
            size=${this.size}
            >+${this.selectedOptions.length-index}</wa-tag
          >
        `;return null})}updated(changedProperties){super.updated(changedProperties),(changedProperties.has("value")||changedProperties.has("displayLabel"))&&this.customStates.set("blank",!this.value&&!this.displayLabel)}handleDisabledChange(){this.disabled&&this.open&&(this.open=!1)}handleValueChange(){let allOptions=this.getAllOptions(),value=Array.isArray(this.value)?this.value:[this.value],selectedOptions=allOptions.filter(el=>value.includes(el.value));this.setSelectedOptions(selectedOptions),this.updateValidity()}async handleOpenChange(){if(this.open&&!this.disabled){this.setCurrentOption(this.selectedOptions[0]||this.getFirstOption());let waShowEvent=new WaShowEvent;if(this.dispatchEvent(waShowEvent),waShowEvent.defaultPrevented){this.open=!1;return}this.addOpenListeners(),this.listbox.hidden=!1,this.popup.active=!0,requestAnimationFrame(()=>{this.setCurrentOption(this.currentOption)}),await animateWithClass(this.popup.popup,"show"),this.currentOption&&scrollIntoView(this.currentOption,this.listbox,"vertical","auto"),this.dispatchEvent(new WaAfterShowEvent)}else{let waHideEvent=new WaHideEvent;if(this.dispatchEvent(waHideEvent),waHideEvent.defaultPrevented){this.open=!1;return}this.removeOpenListeners(),await animateWithClass(this.popup.popup,"hide"),this.listbox.hidden=!0,this.popup.active=!1,this.dispatchEvent(new WaAfterHideEvent)}}async show(){if(this.open||this.disabled){this.open=!1;return}return this.open=!0,waitForEvent(this,"wa-after-show")}async hide(){if(!this.open||this.disabled){this.open=!1;return}return this.open=!1,waitForEvent(this,"wa-after-hide")}focus(options){this.displayInput.focus(options)}blur(){this.displayInput.blur()}formResetCallback(){this.selectionOrder.clear(),this.value=this.defaultValue,super.formResetCallback(),this.handleValueChange(),this.updateComplete.then(()=>{this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0})),this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}render(){let hasLabelSlot=this.hasSlotController.test("label","withLabel"),hasHintSlot=this.hasSlotController.test("hint","withHint"),hasLabel=this.label?!0:!!hasLabelSlot,hasHint=this.hint?!0:!!hasHintSlot,hasClearIcon=(this.hasUpdated||!1)&&this.withClear&&!this.disabled&&(this.displayLabel||this.value&&this.value.length>0);return b2`
      <div
        part="form-control"
        class=${e7({"form-control":!0,"form-control-has-label":hasLabel})}
      >
        <label
          id="label"
          part="form-control-label label"
          class=${e7({label:!0,"has-label":hasLabel})}
          aria-hidden=${hasLabel?"false":"true"}
          @click=${this.handleLabelClick}
        >
          <slot name="label">${this.label}</slot>
        </label>

        <div part="form-control-input" class="form-control-input">
          <wa-popup
            class=${e7({select:!0,open:this.open,disabled:this.disabled,enabled:!this.disabled,multiple:this.multiple})}
            placement=${this.placement}
            flip
            shift
            sync="width"
            auto-size="vertical"
            auto-size-padding="10"
          >
            <div
              part="combobox"
              class="combobox"
              slot="anchor"
              @keydown=${this.handleComboboxKeyDown}
              @mousedown=${this.handleComboboxMouseDown}
              @click=${this.handleComboboxClick}
            >
              <slot part="start" name="start" class="start"></slot>

              <input
                part="display-input"
                class="display-input"
                type="text"
                placeholder=${this.placeholder}
                .disabled=${this.disabled}
                .value=${this.displayLabel}
                ?required=${this.required}
                autocomplete="off"
                spellcheck="false"
                autocapitalize="off"
                readonly
                aria-invalid=${!this.validity.valid}
                aria-controls="listbox"
                aria-expanded=${this.open?"true":"false"}
                aria-haspopup="listbox"
                aria-labelledby="label"
                aria-disabled=${this.disabled?"true":"false"}
                aria-describedby="hint"
                role="combobox"
                tabindex="0"
                @focus=${this.handleFocus}
              />

              <!-- Tags need to wait for first hydration before populating otherwise it will create a hydration mismatch. -->
              ${this.multiple&&this.hasUpdated?b2`<div part="tags" class="tags" @wa-remove=${this.handleTagRemove}>${this.tags}</div>`:""}

              <input
                class="value-input"
                type="text"
                ?disabled=${this.disabled}
                ?required=${this.required}
                .value=${Array.isArray(this.value)?this.value.join(", "):this.value}
                tabindex="-1"
                aria-hidden="true"
                @focus=${()=>this.focus()}
              />

              ${hasClearIcon?b2`
                    <button
                      part="clear-button"
                      type="button"
                      aria-label=${this.localize.term("clearEntry")}
                      @mousedown=${this.handleClearMouseDown}
                      @click=${this.handleClearClick}
                      tabindex="-1"
                    >
                      <slot name="clear-icon">
                        <wa-icon name="circle-xmark" library="system" variant="regular"></wa-icon>
                      </slot>
                    </button>
                  `:""}

              <slot name="end" part="end" class="end"></slot>

              <slot name="expand-icon" part="expand-icon" class="expand-icon">
                <wa-icon library="system" name="chevron-down" variant="solid"></wa-icon>
              </slot>
            </div>

            <div
              id="listbox"
              role="listbox"
              aria-expanded=${this.open?"true":"false"}
              aria-multiselectable=${this.multiple?"true":"false"}
              aria-labelledby="label"
              part="listbox"
              class="listbox"
              tabindex="-1"
              @mouseup=${this.handleOptionClick}
            >
              <slot @slotchange=${this.handleDefaultSlotChange}></slot>
            </div>
          </wa-popup>
        </div>

        <slot
          id="hint"
          name="hint"
          part="hint"
          class=${e7({"has-slotted":hasHint})}
          aria-hidden=${hasHint?"false":"true"}
          >${this.hint}</slot
        >
      </div>
    `}};WaSelect.css=[select_styles_default,form_control_styles_default,size_styles_default];__decorateClass([e5(".select")],WaSelect.prototype,"popup",2);__decorateClass([e5(".combobox")],WaSelect.prototype,"combobox",2);__decorateClass([e5(".display-input")],WaSelect.prototype,"displayInput",2);__decorateClass([e5(".value-input")],WaSelect.prototype,"valueInput",2);__decorateClass([e5(".listbox")],WaSelect.prototype,"listbox",2);__decorateClass([r5()],WaSelect.prototype,"displayLabel",2);__decorateClass([r5()],WaSelect.prototype,"currentOption",2);__decorateClass([r5()],WaSelect.prototype,"selectedOptions",2);__decorateClass([n4({reflect:!0})],WaSelect.prototype,"name",2);__decorateClass([n4({attribute:!1})],WaSelect.prototype,"defaultValue",1);__decorateClass([n4({attribute:"value",reflect:!1})],WaSelect.prototype,"value",1);__decorateClass([n4({reflect:!0})],WaSelect.prototype,"size",2);__decorateClass([watch("size")],WaSelect.prototype,"handleSizeChange",1);__decorateClass([n4()],WaSelect.prototype,"placeholder",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaSelect.prototype,"multiple",2);__decorateClass([n4({attribute:"max-options-visible",type:Number})],WaSelect.prototype,"maxOptionsVisible",2);__decorateClass([n4({type:Boolean})],WaSelect.prototype,"disabled",2);__decorateClass([n4({attribute:"with-clear",type:Boolean})],WaSelect.prototype,"withClear",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaSelect.prototype,"open",2);__decorateClass([n4({reflect:!0})],WaSelect.prototype,"appearance",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaSelect.prototype,"pill",2);__decorateClass([n4()],WaSelect.prototype,"label",2);__decorateClass([n4({reflect:!0})],WaSelect.prototype,"placement",2);__decorateClass([n4({attribute:"hint"})],WaSelect.prototype,"hint",2);__decorateClass([n4({attribute:"with-label",type:Boolean})],WaSelect.prototype,"withLabel",2);__decorateClass([n4({attribute:"with-hint",type:Boolean})],WaSelect.prototype,"withHint",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaSelect.prototype,"required",2);__decorateClass([n4({attribute:!1})],WaSelect.prototype,"getTag",2);__decorateClass([watch("disabled",{waitUntilFirstUpdate:!0})],WaSelect.prototype,"handleDisabledChange",1);__decorateClass([watch("value",{waitUntilFirstUpdate:!0})],WaSelect.prototype,"handleValueChange",1);__decorateClass([watch("open",{waitUntilFirstUpdate:!0})],WaSelect.prototype,"handleOpenChange",1);WaSelect=__decorateClass([t3("wa-select")],WaSelect);WaSelect.disableWarning?.("change-in-update");var WaRemoveEvent=class extends Event{constructor(){super("wa-remove",{bubbles:!0,cancelable:!1,composed:!0})}};var tag_styles_default=i`
  @layer wa-component {
    :host {
      display: inline-flex;
      gap: 0.5em;
      border-radius: var(--wa-border-radius-m);
      align-items: center;
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
      border-style: var(--wa-border-style);
      border-width: var(--wa-border-width-s);
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      font-size: inherit;
      line-height: 1;
      white-space: nowrap;
      user-select: none;
      -webkit-user-select: none;
      height: calc(var(--wa-form-control-height) * 0.8);
      line-height: calc(var(--wa-form-control-height) - var(--wa-form-control-border-width) * 2);
      padding: 0 0.75em;
    }

    /* Appearance modifiers */
    :host([appearance='outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: transparent;
      border-color: var(--wa-color-border-loud, var(--wa-color-neutral-border-loud));
    }

    :host([appearance='filled']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: transparent;
    }

    :host([appearance='filled-outlined']) {
      color: var(--wa-color-on-quiet, var(--wa-color-neutral-on-quiet));
      background-color: var(--wa-color-fill-quiet, var(--wa-color-neutral-fill-quiet));
      border-color: var(--wa-color-border-normal, var(--wa-color-neutral-border-normal));
    }

    :host([appearance='accent']) {
      color: var(--wa-color-on-loud, var(--wa-color-neutral-on-loud));
      background-color: var(--wa-color-fill-loud, var(--wa-color-neutral-fill-loud));
      border-color: transparent;
    }
  }

  .content {
    font-size: var(--wa-font-size-smaller);
  }

  [part='remove-button'] {
    line-height: 1;
  }

  [part='remove-button']::part(base) {
    padding: 0;
    height: 1em;
    width: 1em;
    color: currentColor;
  }

  @media (hover: hover) {
    :host(:hover) > [part='remove-button']::part(base) {
      background-color: transparent;
      color: color-mix(in oklab, currentColor, var(--wa-color-mix-hover));
    }
  }

  :host(:active) > [part='remove-button']::part(base) {
    background-color: transparent;
    color: color-mix(in oklab, currentColor, var(--wa-color-mix-active));
  }

  /*
   * Pill modifier
   */
  :host([pill]) {
    border-radius: var(--wa-border-radius-pill);
  }
`;var WaTag=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.variant="neutral",this.appearance="filled-outlined",this.size="m",this.pill=!1,this.withRemove=!1}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}handleRemoveClick(){this.dispatchEvent(new WaRemoveEvent)}render(){return b2`
      <slot part="content" class="content"></slot>

      ${this.withRemove?b2`
            <wa-button
              part="remove-button"
              exportparts="base:remove-button__base"
              class="remove"
              appearance="plain"
              size=${this.size}
              @click=${this.handleRemoveClick}
              tabindex="-1"
            >
              <wa-icon name="xmark" library="system" variant="solid" label=${this.localize.term("remove")}></wa-icon>
            </wa-button>
          `:""}
    `}};WaTag.css=[tag_styles_default,variants_styles_default,size_styles_default];__decorateClass([n4({reflect:!0})],WaTag.prototype,"variant",2);__decorateClass([n4({reflect:!0})],WaTag.prototype,"appearance",2);__decorateClass([n4({reflect:!0})],WaTag.prototype,"size",2);__decorateClass([watch("size")],WaTag.prototype,"handleSizeChange",1);__decorateClass([n4({type:Boolean,reflect:!0})],WaTag.prototype,"pill",2);__decorateClass([n4({attribute:"with-remove",type:Boolean})],WaTag.prototype,"withRemove",2);WaTag=__decorateClass([t3("wa-tag")],WaTag);var WaRepositionEvent=class extends Event{constructor(){super("wa-reposition",{bubbles:!0,cancelable:!1,composed:!0})}};var popup_styles_default=i`
  :host {
    --arrow-color: black;
    --arrow-size: var(--wa-tooltip-arrow-size);
    --popup-border-width: 0px;
    --show-duration: var(--wa-transition-fast);
    --hide-duration: var(--wa-transition-fast);

    /*
     * These properties are computed to account for the arrow's dimensions after being rotated 45º. The constant
     * 0.7071 is derived from sin(45) to calculate the length of the arrow after rotation.
     *
     * The diamond will be translated inward by --arrow-base-offset, the border thickness, to centralise it on
     * the inner edge of the popup border. This also means we need to increase the size of the arrow by the
     * same amount to compensate.
     *
     * A diamond shaped clipping mask is used to avoid overlap of popup content. This extends slightly inward so
     * the popup border is covered with no sub-pixel rounding artifacts. The diamond corners are mitred at 22.5º
     * to properly merge any arrow border with the popup border. The constant 1.4142 is derived from 1 + tan(22.5).
     *
     */
    --arrow-base-offset: var(--popup-border-width);
    --arrow-size-diagonal: calc((var(--arrow-size) + var(--arrow-base-offset)) * 0.7071);
    --arrow-padding-offset: calc(var(--arrow-size-diagonal) - var(--arrow-size));
    --arrow-size-div: calc(var(--arrow-size-diagonal) * 2);
    --arrow-clipping-corner: calc(var(--arrow-base-offset) * 1.4142);

    display: contents;
  }

  .popup {
    position: absolute;
    isolation: isolate;
    max-width: var(--auto-size-available-width, none);
    max-height: var(--auto-size-available-height, none);

    /* Clear UA styles for [popover] */
    :where(&) {
      inset: unset;
      padding: unset;
      margin: unset;
      width: unset;
      height: unset;
      color: unset;
      background: unset;
      border: unset;
      overflow: unset;
    }
  }

  .popup-fixed {
    position: fixed;
  }

  .popup:not(.popup-active) {
    display: none;
  }

  .arrow {
    position: absolute;
    width: var(--arrow-size-div);
    height: var(--arrow-size-div);
    background: var(--arrow-color);
    z-index: 3;
    clip-path: polygon(
      var(--arrow-clipping-corner) 100%,
      var(--arrow-base-offset) calc(100% - var(--arrow-base-offset)),
      calc(var(--arrow-base-offset) - 2px) calc(100% - var(--arrow-base-offset)),
      calc(100% - var(--arrow-base-offset)) calc(var(--arrow-base-offset) - 2px),
      calc(100% - var(--arrow-base-offset)) var(--arrow-base-offset),
      100% var(--arrow-clipping-corner),
      100% 100%
    );
    rotate: 45deg;
  }

  :host([data-current-placement|='left']) .arrow {
    rotate: -45deg;
  }

  :host([data-current-placement|='right']) .arrow {
    rotate: 135deg;
  }

  :host([data-current-placement|='bottom']) .arrow {
    rotate: 225deg;
  }

  /* Hover bridge */
  .popup-hover-bridge:not(.popup-hover-bridge-visible) {
    display: none;
  }

  .popup-hover-bridge {
    position: fixed;
    z-index: 899;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    clip-path: polygon(
      var(--hover-bridge-top-left-x, 0) var(--hover-bridge-top-left-y, 0),
      var(--hover-bridge-top-right-x, 0) var(--hover-bridge-top-right-y, 0),
      var(--hover-bridge-bottom-right-x, 0) var(--hover-bridge-bottom-right-y, 0),
      var(--hover-bridge-bottom-left-x, 0) var(--hover-bridge-bottom-left-y, 0)
    );
  }

  /* Built-in animations */
  .show {
    animation: show var(--show-duration) ease;
  }

  .hide {
    animation: show var(--hide-duration) ease reverse;
  }

  @keyframes show {
    from {
      opacity: 0;
    }
    to {
      opacity: 1;
    }
  }

  .show-with-scale {
    animation: show-with-scale var(--show-duration) ease;
  }

  .hide-with-scale {
    animation: show-with-scale var(--hide-duration) ease reverse;
  }

  @keyframes show-with-scale {
    from {
      opacity: 0;
      scale: 0.8;
    }
    to {
      opacity: 1;
      scale: 1;
    }
  }
`;var min=Math.min,max=Math.max,round=Math.round,floor=Math.floor,createCoords=v2=>({x:v2,y:v2}),oppositeSideMap={left:"right",right:"left",bottom:"top",top:"bottom"};function clamp(start,value,end){return max(start,min(value,end))}function evaluate(value,param){return typeof value=="function"?value(param):value}function getSide(placement){return placement.split("-")[0]}function getAlignment(placement){return placement.split("-")[1]}function getOppositeAxis(axis){return axis==="x"?"y":"x"}function getAxisLength(axis){return axis==="y"?"height":"width"}function getSideAxis(placement){let firstChar=placement[0];return firstChar==="t"||firstChar==="b"?"y":"x"}function getAlignmentAxis(placement){return getOppositeAxis(getSideAxis(placement))}function getAlignmentSides(placement,rects,rtl){rtl===void 0&&(rtl=!1);let alignment=getAlignment(placement),alignmentAxis=getAlignmentAxis(placement),length=getAxisLength(alignmentAxis),mainAlignmentSide=alignmentAxis==="x"?alignment===(rtl?"end":"start")?"right":"left":alignment==="start"?"bottom":"top";return rects.reference[length]>rects.floating[length]&&(mainAlignmentSide=getOppositePlacement(mainAlignmentSide)),[mainAlignmentSide,getOppositePlacement(mainAlignmentSide)]}function getExpandedPlacements(placement){let oppositePlacement=getOppositePlacement(placement);return[getOppositeAlignmentPlacement(placement),oppositePlacement,getOppositeAlignmentPlacement(oppositePlacement)]}function getOppositeAlignmentPlacement(placement){return placement.includes("start")?placement.replace("start","end"):placement.replace("end","start")}var lrPlacement=["left","right"],rlPlacement=["right","left"],tbPlacement=["top","bottom"],btPlacement=["bottom","top"];function getSideList(side,isStart,rtl){switch(side){case"top":case"bottom":return rtl?isStart?rlPlacement:lrPlacement:isStart?lrPlacement:rlPlacement;case"left":case"right":return isStart?tbPlacement:btPlacement;default:return[]}}function getOppositeAxisPlacements(placement,flipAlignment,direction,rtl){let alignment=getAlignment(placement),list=getSideList(getSide(placement),direction==="start",rtl);return alignment&&(list=list.map(side=>side+"-"+alignment),flipAlignment&&(list=list.concat(list.map(getOppositeAlignmentPlacement)))),list}function getOppositePlacement(placement){let side=getSide(placement);return oppositeSideMap[side]+placement.slice(side.length)}function expandPaddingObject(padding){var _padding$top,_padding$right,_padding$bottom,_padding$left;return{top:(_padding$top=padding.top)!=null?_padding$top:0,right:(_padding$right=padding.right)!=null?_padding$right:0,bottom:(_padding$bottom=padding.bottom)!=null?_padding$bottom:0,left:(_padding$left=padding.left)!=null?_padding$left:0}}function getPaddingObject(padding){return typeof padding!="number"?expandPaddingObject(padding):{top:padding,right:padding,bottom:padding,left:padding}}function rectToClientRect(rect){let{x:x2,y:y3,width,height}=rect;return{width,height,top:y3,left:x2,right:x2+width,bottom:y3+height,x:x2,y:y3}}function computeCoordsFromPlacement(_ref,placement,rtl){let{reference,floating}=_ref,sideAxis=getSideAxis(placement),alignmentAxis=getAlignmentAxis(placement),alignLength=getAxisLength(alignmentAxis),side=getSide(placement),isVertical=sideAxis==="y",commonX=reference.x+reference.width/2-floating.width/2,commonY=reference.y+reference.height/2-floating.height/2,commonAlign=reference[alignLength]/2-floating[alignLength]/2,coords;switch(side){case"top":coords={x:commonX,y:reference.y-floating.height};break;case"bottom":coords={x:commonX,y:reference.y+reference.height};break;case"right":coords={x:reference.x+reference.width,y:commonY};break;case"left":coords={x:reference.x-floating.width,y:commonY};break;default:coords={x:reference.x,y:reference.y}}let alignment=getAlignment(placement);return alignment&&(coords[alignmentAxis]+=commonAlign*(alignment==="end"?1:-1)*(rtl&&isVertical?-1:1)),coords}async function detectOverflow(state,options){var _await$platform$isEle;options===void 0&&(options={});let{x:x2,y:y3,platform:platform2,rects,elements,strategy}=state,{boundary="clippingAncestors",rootBoundary="viewport",elementContext="floating",altBoundary=!1,padding=0}=evaluate(options,state),paddingObject=getPaddingObject(padding),element=elements[altBoundary?elementContext==="floating"?"reference":"floating":elementContext],clippingClientRect=rectToClientRect(await platform2.getClippingRect({element:(_await$platform$isEle=await(platform2.isElement==null?void 0:platform2.isElement(element)))==null||_await$platform$isEle?element:element.contextElement||await(platform2.getDocumentElement==null?void 0:platform2.getDocumentElement(elements.floating)),boundary,rootBoundary,strategy})),rect=elementContext==="floating"?{x:x2,y:y3,width:rects.floating.width,height:rects.floating.height}:rects.reference,offsetParent=await(platform2.getOffsetParent==null?void 0:platform2.getOffsetParent(elements.floating)),offsetScale=await(platform2.isElement==null?void 0:platform2.isElement(offsetParent))&&await(platform2.getScale==null?void 0:platform2.getScale(offsetParent))||{x:1,y:1},elementClientRect=rectToClientRect(platform2.convertOffsetParentRelativeRectToViewportRelativeRect?await platform2.convertOffsetParentRelativeRectToViewportRelativeRect({elements,rect,offsetParent,strategy}):rect);return{top:(clippingClientRect.top-elementClientRect.top+paddingObject.top)/offsetScale.y,bottom:(elementClientRect.bottom-clippingClientRect.bottom+paddingObject.bottom)/offsetScale.y,left:(clippingClientRect.left-elementClientRect.left+paddingObject.left)/offsetScale.x,right:(elementClientRect.right-clippingClientRect.right+paddingObject.right)/offsetScale.x}}var MAX_RESET_COUNT=50,computePosition=async(reference,floating,config)=>{let{placement="bottom",strategy="absolute",middleware=[],platform:platform2}=config,platformWithDetectOverflow=platform2.detectOverflow?platform2:{...platform2,detectOverflow},rtl=await(platform2.isRTL==null?void 0:platform2.isRTL(floating)),rects=await platform2.getElementRects({reference,floating,strategy}),{x:x2,y:y3}=computeCoordsFromPlacement(rects,placement,rtl),statefulPlacement=placement,resetCount=0,middlewareData={};for(let i8=0;i8<middleware.length;i8++){let currentMiddleware=middleware[i8];if(!currentMiddleware)continue;let{name,fn}=currentMiddleware,{x:nextX,y:nextY,data,reset}=await fn({x:x2,y:y3,initialPlacement:placement,placement:statefulPlacement,strategy,middlewareData,rects,platform:platformWithDetectOverflow,elements:{reference,floating}});x2=nextX??x2,y3=nextY??y3,middlewareData[name]={...middlewareData[name],...data},reset&&resetCount<MAX_RESET_COUNT&&(resetCount++,typeof reset=="object"&&(reset.placement&&(statefulPlacement=reset.placement),reset.rects&&(rects=reset.rects===!0?await platform2.getElementRects({reference,floating,strategy}):reset.rects),{x:x2,y:y3}=computeCoordsFromPlacement(rects,statefulPlacement,rtl)),i8=-1)}return{x:x2,y:y3,placement:statefulPlacement,strategy,middlewareData}},arrow=options=>({name:"arrow",options,async fn(state){let{x:x2,y:y3,placement,rects,platform:platform2,elements,middlewareData}=state,{element,padding=0}=evaluate(options,state)||{};if(element==null)return{};let paddingObject=getPaddingObject(padding),coords={x:x2,y:y3},axis=getAlignmentAxis(placement),length=getAxisLength(axis),arrowDimensions=await platform2.getDimensions(element),isYAxis=axis==="y",minProp=isYAxis?"top":"left",maxProp=isYAxis?"bottom":"right",clientProp=isYAxis?"clientHeight":"clientWidth",endDiff=rects.reference[length]+rects.reference[axis]-coords[axis]-rects.floating[length],startDiff=coords[axis]-rects.reference[axis],arrowOffsetParent=await(platform2.getOffsetParent==null?void 0:platform2.getOffsetParent(element)),clientSize=arrowOffsetParent?arrowOffsetParent[clientProp]:0;(!clientSize||!await(platform2.isElement==null?void 0:platform2.isElement(arrowOffsetParent)))&&(clientSize=elements.floating[clientProp]||rects.floating[length]);let centerToReference=endDiff/2-startDiff/2,largestPossiblePadding=clientSize/2-arrowDimensions[length]/2-1,minPadding=min(paddingObject[minProp],largestPossiblePadding),maxPadding=min(paddingObject[maxProp],largestPossiblePadding),max2=clientSize-arrowDimensions[length]-maxPadding,center=clientSize/2-arrowDimensions[length]/2+centerToReference,offset3=clamp(minPadding,center,max2),shouldAddOffset=!middlewareData.arrow&&getAlignment(placement)!=null&&center!==offset3&&rects.reference[length]/2-(center<minPadding?minPadding:maxPadding)-arrowDimensions[length]/2<0,alignmentOffset=shouldAddOffset?center<minPadding?center-minPadding:center-max2:0;return{[axis]:coords[axis]+alignmentOffset,data:{[axis]:offset3,centerOffset:center-offset3-alignmentOffset,...shouldAddOffset&&{alignmentOffset}},reset:shouldAddOffset}}});var flip=function(options){return options===void 0&&(options={}),{name:"flip",options,async fn(state){var _middlewareData$arrow,_middlewareData$flip;let{placement,middlewareData,rects,initialPlacement,platform:platform2,elements}=state,{mainAxis:checkMainAxis=!0,crossAxis:checkCrossAxis=!0,fallbackPlacements:specifiedFallbackPlacements,fallbackStrategy="bestFit",fallbackAxisSideDirection="none",flipAlignment=!0,...detectOverflowOptions}=evaluate(options,state);if((_middlewareData$arrow=middlewareData.arrow)!=null&&_middlewareData$arrow.alignmentOffset)return{};let side=getSide(placement),initialSideAxis=getSideAxis(initialPlacement),isBasePlacement=getSide(initialPlacement)===initialPlacement,rtl=await(platform2.isRTL==null?void 0:platform2.isRTL(elements.floating)),fallbackPlacements=specifiedFallbackPlacements||(isBasePlacement||!flipAlignment?[getOppositePlacement(initialPlacement)]:getExpandedPlacements(initialPlacement)),hasFallbackAxisSideDirection=fallbackAxisSideDirection!=="none";!specifiedFallbackPlacements&&hasFallbackAxisSideDirection&&fallbackPlacements.push(...getOppositeAxisPlacements(initialPlacement,flipAlignment,fallbackAxisSideDirection,rtl));let placements2=[initialPlacement,...fallbackPlacements],overflow=await platform2.detectOverflow(state,detectOverflowOptions),overflows=[],overflowsData=((_middlewareData$flip=middlewareData.flip)==null?void 0:_middlewareData$flip.overflows)||[];if(checkMainAxis&&overflows.push(overflow[side]),checkCrossAxis){let sides2=getAlignmentSides(placement,rects,rtl);overflows.push(overflow[sides2[0]],overflow[sides2[1]])}if(overflowsData=[...overflowsData,{placement,overflows}],!overflows.every(side2=>side2<=0)){var _middlewareData$flip2,_overflowsData$filter;let nextIndex=(((_middlewareData$flip2=middlewareData.flip)==null?void 0:_middlewareData$flip2.index)||0)+1,nextPlacement=placements2[nextIndex];if(nextPlacement&&(!(checkCrossAxis==="alignment"?initialSideAxis!==getSideAxis(nextPlacement):!1)||overflowsData.every(d3=>getSideAxis(d3.placement)===initialSideAxis?d3.overflows[0]>0:!0)))return{data:{index:nextIndex,overflows:overflowsData},reset:{placement:nextPlacement}};let resetPlacement=(_overflowsData$filter=overflowsData.filter(d3=>d3.overflows[0]<=0).sort((a4,b3)=>a4.overflows[1]-b3.overflows[1])[0])==null?void 0:_overflowsData$filter.placement;if(!resetPlacement)switch(fallbackStrategy){case"bestFit":{var _overflowsData$filter2;let placement2=(_overflowsData$filter2=overflowsData.filter(d3=>{if(hasFallbackAxisSideDirection){let currentSideAxis=getSideAxis(d3.placement);return currentSideAxis===initialSideAxis||currentSideAxis==="y"}return!0}).map(d3=>[d3.placement,d3.overflows.filter(overflow2=>overflow2>0).reduce((acc,overflow2)=>acc+overflow2,0)]).sort((a4,b3)=>a4[1]-b3[1])[0])==null?void 0:_overflowsData$filter2[0];placement2&&(resetPlacement=placement2);break}case"initialPlacement":resetPlacement=initialPlacement;break}if(placement!==resetPlacement)return{reset:{placement:resetPlacement}}}return{}}}};var originSides=new Set(["left","top"]);async function convertValueToCoords(state,options){let{placement,platform:platform2,elements}=state,rtl=await(platform2.isRTL==null?void 0:platform2.isRTL(elements.floating)),side=getSide(placement),alignment=getAlignment(placement),isVertical=getSideAxis(placement)==="y",mainAxisMulti=originSides.has(side)?-1:1,crossAxisMulti=rtl&&isVertical?-1:1,rawValue=evaluate(options,state),{mainAxis,crossAxis,alignmentAxis}=typeof rawValue=="number"?{mainAxis:rawValue,crossAxis:0,alignmentAxis:null}:{mainAxis:rawValue.mainAxis||0,crossAxis:rawValue.crossAxis||0,alignmentAxis:rawValue.alignmentAxis};return alignment&&typeof alignmentAxis=="number"&&(crossAxis=alignment==="end"?alignmentAxis*-1:alignmentAxis),isVertical?{x:crossAxis*crossAxisMulti,y:mainAxis*mainAxisMulti}:{x:mainAxis*mainAxisMulti,y:crossAxis*crossAxisMulti}}var offset=function(options){return options===void 0&&(options=0),{name:"offset",options,async fn(state){var _middlewareData$offse,_middlewareData$arrow;let{x:x2,y:y3,placement,middlewareData}=state,diffCoords=await convertValueToCoords(state,options);return placement===((_middlewareData$offse=middlewareData.offset)==null?void 0:_middlewareData$offse.placement)&&(_middlewareData$arrow=middlewareData.arrow)!=null&&_middlewareData$arrow.alignmentOffset?{}:{x:x2+diffCoords.x,y:y3+diffCoords.y,data:{...diffCoords,placement}}}}},shift=function(options){return options===void 0&&(options={}),{name:"shift",options,async fn(state){let{x:x2,y:y3,placement,platform:platform2}=state,{mainAxis:checkMainAxis=!0,crossAxis:checkCrossAxis=!1,limiter={fn:_ref=>{let{x:x3,y:y4}=_ref;return{x:x3,y:y4}}},...detectOverflowOptions}=evaluate(options,state),coords={x:x2,y:y3},overflow=await platform2.detectOverflow(state,detectOverflowOptions),crossAxis=getSideAxis(placement),mainAxis=getOppositeAxis(crossAxis),mainAxisCoord=coords[mainAxis],crossAxisCoord=coords[crossAxis],clampCoord=(axis,coord)=>clamp(coord+overflow[axis==="y"?"top":"left"],coord,coord-overflow[axis==="y"?"bottom":"right"]);checkMainAxis&&(mainAxisCoord=clampCoord(mainAxis,mainAxisCoord)),checkCrossAxis&&(crossAxisCoord=clampCoord(crossAxis,crossAxisCoord));let limitedCoords=limiter.fn({...state,[mainAxis]:mainAxisCoord,[crossAxis]:crossAxisCoord});return{...limitedCoords,data:{x:limitedCoords.x-x2,y:limitedCoords.y-y3,enabled:{[mainAxis]:checkMainAxis,[crossAxis]:checkCrossAxis}}}}}};var size=function(options){return options===void 0&&(options={}),{name:"size",options,async fn(state){let{placement,rects,platform:platform2,elements}=state,{apply=()=>{},...detectOverflowOptions}=evaluate(options,state),overflow=await platform2.detectOverflow(state,detectOverflowOptions),side=getSide(placement),alignment=getAlignment(placement),isYAxis=getSideAxis(placement)==="y",{width,height}=rects.floating,heightSide,widthSide;side==="top"||side==="bottom"?(heightSide=side,widthSide=alignment===(await(platform2.isRTL==null?void 0:platform2.isRTL(elements.floating))?"start":"end")?"left":"right"):(widthSide=side,heightSide=alignment==="end"?"top":"bottom");let maximumClippingHeight=height-overflow.top-overflow.bottom,maximumClippingWidth=width-overflow.left-overflow.right,overflowAvailableHeight=min(height-overflow[heightSide],maximumClippingHeight),overflowAvailableWidth=min(width-overflow[widthSide],maximumClippingWidth),shiftData=state.middlewareData.shift,noShift=!shiftData,availableHeight=overflowAvailableHeight,availableWidth=overflowAvailableWidth;shiftData!=null&&shiftData.enabled.x&&(availableWidth=maximumClippingWidth),shiftData!=null&&shiftData.enabled.y&&(availableHeight=maximumClippingHeight),noShift&&!alignment&&(isYAxis?availableWidth=width-2*max(overflow.left,overflow.right):availableHeight=height-2*max(overflow.top,overflow.bottom)),await apply({...state,availableWidth,availableHeight});let nextDimensions=await platform2.getDimensions(elements.floating);return width!==nextDimensions.width||height!==nextDimensions.height?{reset:{rects:!0}}:{}}}};function hasWindow(){return typeof window<"u"}function getNodeName(node){return isNode(node)?(node.nodeName||"").toLowerCase():"#document"}function getWindow(node){var _node$ownerDocument;return(node==null||(_node$ownerDocument=node.ownerDocument)==null?void 0:_node$ownerDocument.defaultView)||window}function getDocumentElement(node){var _ref;return(_ref=(isNode(node)?node.ownerDocument:node.document)||window.document)==null?void 0:_ref.documentElement}function isNode(value){return hasWindow()?value instanceof Node||value instanceof getWindow(value).Node:!1}function isElement(value){return hasWindow()?value instanceof Element||value instanceof getWindow(value).Element:!1}function isHTMLElement(value){return hasWindow()?value instanceof HTMLElement||value instanceof getWindow(value).HTMLElement:!1}function isShadowRoot(value){return!hasWindow()||typeof ShadowRoot>"u"?!1:value instanceof ShadowRoot||value instanceof getWindow(value).ShadowRoot}function isOverflowElement(element){let{overflow,overflowX,overflowY,display}=getComputedStyle2(element);return/auto|scroll|overlay|hidden|clip/.test(overflow+overflowY+overflowX)&&display!=="inline"&&display!=="contents"}function isTableElement(element){return/^(table|td|th)$/.test(getNodeName(element))}function isTopLayer(element){try{if(element.matches(":popover-open"))return!0}catch{}try{return element.matches(":modal")}catch{return!1}}var willChangeRe=/transform|translate|scale|rotate|perspective|filter/,containRe=/paint|layout|strict|content/,isNotNone=value=>!!value&&value!=="none",isWebKitValue;function isContainingBlock(elementOrCss){let css=isElement(elementOrCss)?getComputedStyle2(elementOrCss):elementOrCss;return isNotNone(css.transform)||isNotNone(css.translate)||isNotNone(css.scale)||isNotNone(css.rotate)||isNotNone(css.perspective)||!isWebKit()&&(isNotNone(css.backdropFilter)||isNotNone(css.filter))||willChangeRe.test(css.willChange||"")||containRe.test(css.contain||"")}function getContainingBlock(element){let currentNode=getParentNode(element);for(;isHTMLElement(currentNode)&&!isLastTraversableNode(currentNode);){if(isContainingBlock(currentNode))return currentNode;if(isTopLayer(currentNode))return null;currentNode=getParentNode(currentNode)}return null}function isWebKit(){return isWebKitValue==null&&(isWebKitValue=typeof CSS<"u"&&CSS.supports&&CSS.supports("-webkit-backdrop-filter","none")),isWebKitValue}function isLastTraversableNode(node){return/^(html|body|#document)$/.test(getNodeName(node))}function getComputedStyle2(element){return getWindow(element).getComputedStyle(element)}function getNodeScroll(element){return isElement(element)?{scrollLeft:element.scrollLeft,scrollTop:element.scrollTop}:{scrollLeft:element.scrollX,scrollTop:element.scrollY}}function getParentNode(node){if(getNodeName(node)==="html")return node;let result=node.assignedSlot||node.parentNode||isShadowRoot(node)&&node.host||getDocumentElement(node);return isShadowRoot(result)?result.host:result}function getNearestOverflowAncestor(node){let parentNode=getParentNode(node);return isLastTraversableNode(parentNode)?(node.ownerDocument||node).body:isHTMLElement(parentNode)&&isOverflowElement(parentNode)?parentNode:getNearestOverflowAncestor(parentNode)}function getOverflowAncestors(node,list,traverseIframes){var _node$ownerDocument2;list===void 0&&(list=[]),traverseIframes===void 0&&(traverseIframes=!0);let scrollableAncestor=getNearestOverflowAncestor(node),isBody=scrollableAncestor===((_node$ownerDocument2=node.ownerDocument)==null?void 0:_node$ownerDocument2.body),win=getWindow(scrollableAncestor);if(isBody){let frameElement=getFrameElement(win);return list.concat(win,win.visualViewport||[],isOverflowElement(scrollableAncestor)?scrollableAncestor:[],frameElement&&traverseIframes?getOverflowAncestors(frameElement):[])}else return list.concat(scrollableAncestor,getOverflowAncestors(scrollableAncestor,[],traverseIframes))}function getFrameElement(win){return win.parent&&Object.getPrototypeOf(win.parent)?win.frameElement:null}function getCssDimensions(element){let css=getComputedStyle2(element),width=parseFloat(css.width)||0,height=parseFloat(css.height)||0,hasOffset=isHTMLElement(element),offsetWidth=hasOffset?element.offsetWidth:width,offsetHeight=hasOffset?element.offsetHeight:height,shouldFallback=round(width)!==offsetWidth||round(height)!==offsetHeight;return shouldFallback&&(width=offsetWidth,height=offsetHeight),{width,height,$:shouldFallback}}function unwrapElement(element){return isElement(element)?element:element.contextElement}function getScale(element){let domElement=unwrapElement(element);if(!isHTMLElement(domElement))return createCoords(1);let rect=domElement.getBoundingClientRect(),{width,height,$:$3}=getCssDimensions(domElement),x2=($3?round(rect.width):rect.width)/width,y3=($3?round(rect.height):rect.height)/height;return(!x2||!Number.isFinite(x2))&&(x2=1),(!y3||!Number.isFinite(y3))&&(y3=1),{x:x2,y:y3}}var noOffsets=createCoords(0);function getVisualOffsets(element){let win=getWindow(element);return!isWebKit()||!win.visualViewport?noOffsets:{x:win.visualViewport.offsetLeft,y:win.visualViewport.offsetTop}}function shouldAddVisualOffsets(element,isFixed,floatingOffsetParent){return isFixed===void 0&&(isFixed=!1),!!floatingOffsetParent&&isFixed&&floatingOffsetParent===getWindow(element)}function getBoundingClientRect(element,includeScale,isFixedStrategy,offsetParent){includeScale===void 0&&(includeScale=!1),isFixedStrategy===void 0&&(isFixedStrategy=!1);let clientRect=element.getBoundingClientRect(),domElement=unwrapElement(element),scale=createCoords(1);includeScale&&(offsetParent?isElement(offsetParent)&&(scale=getScale(offsetParent)):scale=getScale(element));let visualOffsets=shouldAddVisualOffsets(domElement,isFixedStrategy,offsetParent)?getVisualOffsets(domElement):createCoords(0),x2=(clientRect.left+visualOffsets.x)/scale.x,y3=(clientRect.top+visualOffsets.y)/scale.y,width=clientRect.width/scale.x,height=clientRect.height/scale.y;if(domElement&&offsetParent){let win=getWindow(domElement),offsetWin=isElement(offsetParent)?getWindow(offsetParent):offsetParent,currentWin=win,currentIFrame=getFrameElement(currentWin);for(;currentIFrame&&offsetWin!==currentWin;){let iframeScale=getScale(currentIFrame),iframeRect=currentIFrame.getBoundingClientRect(),css=getComputedStyle2(currentIFrame),left=iframeRect.left+(currentIFrame.clientLeft+parseFloat(css.paddingLeft))*iframeScale.x,top=iframeRect.top+(currentIFrame.clientTop+parseFloat(css.paddingTop))*iframeScale.y;x2*=iframeScale.x,y3*=iframeScale.y,width*=iframeScale.x,height*=iframeScale.y,x2+=left,y3+=top,currentWin=getWindow(currentIFrame),currentIFrame=getFrameElement(currentWin)}}return rectToClientRect({width,height,x:x2,y:y3})}function getWindowScrollBarX(element,rect){let leftScroll=getNodeScroll(element).scrollLeft;return rect?rect.left+leftScroll:getBoundingClientRect(getDocumentElement(element)).left+leftScroll}function getHTMLOffset(documentElement,scroll){let htmlRect=documentElement.getBoundingClientRect(),x2=htmlRect.left+scroll.scrollLeft-getWindowScrollBarX(documentElement,htmlRect),y3=htmlRect.top+scroll.scrollTop;return{x:x2,y:y3}}function convertOffsetParentRelativeRectToViewportRelativeRect(_ref){let{elements,rect,offsetParent,strategy}=_ref,isFixed=strategy==="fixed",documentElement=getDocumentElement(offsetParent),topLayer=elements?isTopLayer(elements.floating):!1;if(offsetParent===documentElement||topLayer&&isFixed)return rect;let scroll={scrollLeft:0,scrollTop:0},scale=createCoords(1),offsets=createCoords(0),isOffsetParentAnElement=isHTMLElement(offsetParent);if((isOffsetParentAnElement||!isFixed)&&((getNodeName(offsetParent)!=="body"||isOverflowElement(documentElement))&&(scroll=getNodeScroll(offsetParent)),isOffsetParentAnElement)){let offsetRect=getBoundingClientRect(offsetParent);scale=getScale(offsetParent),offsets.x=offsetRect.x+offsetParent.clientLeft,offsets.y=offsetRect.y+offsetParent.clientTop}let htmlOffset=documentElement&&!isOffsetParentAnElement&&!isFixed?getHTMLOffset(documentElement,scroll):createCoords(0);return{width:rect.width*scale.x,height:rect.height*scale.y,x:rect.x*scale.x-scroll.scrollLeft*scale.x+offsets.x+htmlOffset.x,y:rect.y*scale.y-scroll.scrollTop*scale.y+offsets.y+htmlOffset.y}}function getClientRects(element){return element.getClientRects?Array.from(element.getClientRects()):[]}function getDocumentRect(html){let scroll=getNodeScroll(html),body=html.ownerDocument.body,width=max(html.scrollWidth,html.clientWidth,body.scrollWidth,body.clientWidth),height=max(html.scrollHeight,html.clientHeight,body.scrollHeight,body.clientHeight),x2=-scroll.scrollLeft+getWindowScrollBarX(html),y3=-scroll.scrollTop;return getComputedStyle2(body).direction==="rtl"&&(x2+=max(html.clientWidth,body.clientWidth)-width),{width,height,x:x2,y:y3}}var SCROLLBAR_MAX=25;function getViewportRect(element,strategy,rootBoundary){rootBoundary===void 0&&(rootBoundary="viewport");let isLayoutViewport=rootBoundary==="layoutViewport",win=getWindow(element),html=getDocumentElement(element),visualViewport=win.visualViewport,width=html.clientWidth,height=html.clientHeight,x2=0,y3=0;if(visualViewport){let layoutRelativeClientCoords=!isWebKit()||strategy==="fixed";isLayoutViewport?layoutRelativeClientCoords||(x2=-visualViewport.offsetLeft,y3=-visualViewport.offsetTop):(width=visualViewport.width,height=visualViewport.height,layoutRelativeClientCoords&&(x2=visualViewport.offsetLeft,y3=visualViewport.offsetTop))}if(getWindowScrollBarX(html)<=0){let doc=html.ownerDocument,body=doc.body,bodyStyles=getComputedStyle(body),bodyMarginInline=doc.compatMode==="CSS1Compat"&&parseFloat(bodyStyles.marginLeft)+parseFloat(bodyStyles.marginRight)||0,reservedWidth=Math.abs(html.clientWidth-body.clientWidth-bodyMarginInline),gutter=getComputedStyle(html).scrollbarGutter==="stable both-edges"?reservedWidth/2:reservedWidth;gutter<=SCROLLBAR_MAX&&(width-=gutter)}return{width,height,x:x2,y:y3}}function getInnerBoundingClientRect(element,strategy){let clientRect=getBoundingClientRect(element,!0,strategy==="fixed"),top=clientRect.top+element.clientTop,left=clientRect.left+element.clientLeft,scale=getScale(element),width=element.clientWidth*scale.x,height=element.clientHeight*scale.y,x2=left*scale.x,y3=top*scale.y;return{width,height,x:x2,y:y3}}function getClientRectFromClippingAncestor(element,clippingAncestor,strategy){let rect;if(clippingAncestor==="viewport"||clippingAncestor==="layoutViewport")rect=getViewportRect(element,strategy,clippingAncestor);else if(clippingAncestor==="document")rect=getDocumentRect(getDocumentElement(element));else if(isElement(clippingAncestor))rect=getInnerBoundingClientRect(clippingAncestor,strategy);else{let visualOffsets=getVisualOffsets(element);rect={x:clippingAncestor.x-visualOffsets.x,y:clippingAncestor.y-visualOffsets.y,width:clippingAncestor.width,height:clippingAncestor.height}}return rectToClientRect(rect)}function getClippingElementAncestors(element,cache){let cachedResult=cache.get(element);if(cachedResult)return cachedResult;let result=getOverflowAncestors(element,[],!1).filter(el=>isElement(el)&&getNodeName(el)!=="body"),lastKeptComputedStyle=null,elementIsFixed=getComputedStyle2(element).position==="fixed",currentNode=elementIsFixed?getParentNode(element):element;for(;isElement(currentNode)&&!isLastTraversableNode(currentNode);){let computedStyle=getComputedStyle2(currentNode),currentNodeIsContaining=isContainingBlock(currentNode),lastPosition=lastKeptComputedStyle?lastKeptComputedStyle.position:elementIsFixed?"fixed":"";!currentNodeIsContaining&&(lastPosition==="fixed"||lastPosition==="absolute"&&computedStyle.position==="static")?result=result.filter(ancestor=>ancestor!==currentNode):lastKeptComputedStyle=computedStyle,currentNode=getParentNode(currentNode)}return cache.set(element,result),result}function getClippingRect(_ref){let{element,boundary,rootBoundary,strategy}=_ref,clippingAncestors=[...boundary==="clippingAncestors"?isTopLayer(element)?[]:getClippingElementAncestors(element,this._c):[].concat(boundary),rootBoundary],firstRect=getClientRectFromClippingAncestor(element,clippingAncestors[0],strategy),top=firstRect.top,right=firstRect.right,bottom=firstRect.bottom,left=firstRect.left;for(let i8=1;i8<clippingAncestors.length;i8++){let rect=getClientRectFromClippingAncestor(element,clippingAncestors[i8],strategy);top=max(rect.top,top),right=min(rect.right,right),bottom=min(rect.bottom,bottom),left=max(rect.left,left)}return{width:right-left,height:bottom-top,x:left,y:top}}function getDimensions(element){let{width,height}=getCssDimensions(element);return{width,height}}function getRectRelativeToOffsetParent(element,offsetParent,strategy){let isOffsetParentAnElement=isHTMLElement(offsetParent),documentElement=getDocumentElement(offsetParent),isFixed=strategy==="fixed",rect=getBoundingClientRect(element,!0,isFixed,offsetParent),scroll={scrollLeft:0,scrollTop:0},offsets=createCoords(0);if((isOffsetParentAnElement||!isFixed)&&((getNodeName(offsetParent)!=="body"||isOverflowElement(documentElement))&&(scroll=getNodeScroll(offsetParent)),isOffsetParentAnElement)){let offsetRect=getBoundingClientRect(offsetParent,!0,isFixed,offsetParent);offsets.x=offsetRect.x+offsetParent.clientLeft,offsets.y=offsetRect.y+offsetParent.clientTop}!isOffsetParentAnElement&&documentElement&&(offsets.x=getWindowScrollBarX(documentElement));let htmlOffset=documentElement&&!isOffsetParentAnElement&&!isFixed?getHTMLOffset(documentElement,scroll):createCoords(0),x2=rect.left+scroll.scrollLeft-offsets.x-htmlOffset.x,y3=rect.top+scroll.scrollTop-offsets.y-htmlOffset.y;return{x:x2,y:y3,width:rect.width,height:rect.height}}function isStaticPositioned(element){return getComputedStyle2(element).position==="static"}function getTrueOffsetParent(element,polyfill){if(!isHTMLElement(element)||getComputedStyle2(element).position==="fixed")return null;if(polyfill)return polyfill(element);let rawOffsetParent=element.offsetParent;return getDocumentElement(element)===rawOffsetParent&&(rawOffsetParent=rawOffsetParent.ownerDocument.body),rawOffsetParent}function getOffsetParent(element,polyfill){let win=getWindow(element);if(isTopLayer(element))return win;if(!isHTMLElement(element)){let svgOffsetParent=getParentNode(element);for(;svgOffsetParent&&!isLastTraversableNode(svgOffsetParent);){if(isElement(svgOffsetParent)&&!isStaticPositioned(svgOffsetParent))return svgOffsetParent;svgOffsetParent=getParentNode(svgOffsetParent)}return win}let offsetParent=getTrueOffsetParent(element,polyfill);for(;offsetParent&&isTableElement(offsetParent)&&isStaticPositioned(offsetParent);)offsetParent=getTrueOffsetParent(offsetParent,polyfill);return offsetParent&&isLastTraversableNode(offsetParent)&&isStaticPositioned(offsetParent)&&!isContainingBlock(offsetParent)?win:offsetParent||getContainingBlock(element)||win}var getElementRects=async function(data){let getOffsetParentFn=this.getOffsetParent||getOffsetParent,getDimensionsFn=this.getDimensions,floatingDimensions=await getDimensionsFn(data.floating);return{reference:getRectRelativeToOffsetParent(data.reference,await getOffsetParentFn(data.floating),data.strategy),floating:{x:0,y:0,width:floatingDimensions.width,height:floatingDimensions.height}}};function isRTL(element){return getComputedStyle2(element).direction==="rtl"}var platform={convertOffsetParentRelativeRectToViewportRelativeRect,getDocumentElement,getClippingRect,getOffsetParent,getElementRects,getClientRects,getDimensions,getScale,isElement,isRTL};function rectsAreEqual(a4,b3){return a4.x===b3.x&&a4.y===b3.y&&a4.width===b3.width&&a4.height===b3.height}function observeMove(element,onMove,ancestorResize){let io=null,timeoutId,root=getDocumentElement(element);function cleanup(){var _io;clearTimeout(timeoutId),(_io=io)==null||_io.disconnect(),io=null}function refresh(skip,threshold){skip===void 0&&(skip=!1),threshold===void 0&&(threshold=1),cleanup();let elementRectForRootMargin=element.getBoundingClientRect(),{left,top,width,height}=elementRectForRootMargin;if(skip||onMove(),!width||!height)return;let insetTop=floor(top),insetRight=floor(root.clientWidth-(left+width)),insetBottom=floor(root.clientHeight-(top+height)),insetLeft=floor(left),options={rootMargin:-insetTop+"px "+-insetRight+"px "+-insetBottom+"px "+-insetLeft+"px",threshold:max(0,min(1,threshold))||1},isFirstUpdate=!0;function handleObserve(entries){let ratio=entries[0].intersectionRatio;if(!rectsAreEqual(elementRectForRootMargin,element.getBoundingClientRect()))return refresh();if(ratio!==threshold){if(!isFirstUpdate)return refresh();ratio?refresh(!1,ratio):timeoutId=setTimeout(()=>{refresh(!1,1e-7)},1e3)}isFirstUpdate=!1}try{io=new IntersectionObserver(handleObserve,{...options,root:root.ownerDocument})}catch{io=new IntersectionObserver(handleObserve,options)}io.observe(element)}let win=getWindow(element),handleResize=()=>refresh(ancestorResize);return win.addEventListener("resize",handleResize),refresh(!0),()=>{win.removeEventListener("resize",handleResize),cleanup()}}function autoUpdate(reference,floating,update2,options){options===void 0&&(options={});let{ancestorScroll=!0,ancestorResize=!0,elementResize=typeof ResizeObserver=="function",layoutShift=typeof IntersectionObserver=="function",animationFrame=!1}=options,referenceEl=unwrapElement(reference),ancestors=ancestorScroll||ancestorResize?[...referenceEl?getOverflowAncestors(referenceEl):[],...floating?getOverflowAncestors(floating):[]]:[];ancestors.forEach(ancestor=>{ancestorScroll&&ancestor.addEventListener("scroll",update2),ancestorResize&&ancestor.addEventListener("resize",update2)});let cleanupIo=referenceEl&&layoutShift?observeMove(referenceEl,update2,ancestorResize):null,reobserveFrame=-1,resizeObserver=null;elementResize&&(resizeObserver=new ResizeObserver(_ref=>{let[firstEntry]=_ref;firstEntry&&firstEntry.target===referenceEl&&resizeObserver&&floating&&(resizeObserver.unobserve(floating),cancelAnimationFrame(reobserveFrame),reobserveFrame=requestAnimationFrame(()=>{var _resizeObserver;(_resizeObserver=resizeObserver)==null||_resizeObserver.observe(floating)})),update2()}),referenceEl&&!animationFrame&&resizeObserver.observe(referenceEl),floating&&resizeObserver.observe(floating));let frameId,prevRefRect=animationFrame?getBoundingClientRect(reference):null;animationFrame&&frameLoop();function frameLoop(){let nextRefRect=getBoundingClientRect(reference);prevRefRect&&!rectsAreEqual(prevRefRect,nextRefRect)&&update2(),prevRefRect=nextRefRect,frameId=requestAnimationFrame(frameLoop)}return update2(),()=>{var _resizeObserver2;ancestors.forEach(ancestor=>{ancestorScroll&&ancestor.removeEventListener("scroll",update2),ancestorResize&&ancestor.removeEventListener("resize",update2)}),cleanupIo?.(),(_resizeObserver2=resizeObserver)==null||_resizeObserver2.disconnect(),resizeObserver=null,animationFrame&&cancelAnimationFrame(frameId)}}var offset2=offset;var shift2=shift,flip2=flip,size2=size;var arrow2=arrow;var computePosition2=(reference,floating,options)=>{let cache=new Map,mergedOptions=options??{},platformWithCache={...platform,...mergedOptions.platform,_c:cache};return computePosition(reference,floating,{...mergedOptions,platform:platformWithCache})};function e9(t6){return i7(t6)}function r7(t6){return t6.assignedSlot?t6.assignedSlot:t6.parentNode instanceof ShadowRoot?t6.parentNode.host:t6.parentNode}function i7(e10){for(let t6=e10;t6;t6=r7(t6))if(t6 instanceof Element&&getComputedStyle(t6).display==="none")return null;for(let n6=r7(e10);n6;n6=r7(n6)){if(!(n6 instanceof Element))continue;let e11=getComputedStyle(n6);if(e11.display!=="contents"&&(e11.position!=="static"||isContainingBlock(e11)||n6.tagName==="BODY"))return n6}return null}function isVirtualElement(e10){return e10!==null&&typeof e10=="object"&&"getBoundingClientRect"in e10&&("contextElement"in e10?e10 instanceof Element:!0)}var SUPPORTS_POPOVER=!!globalThis?.HTMLElement?.prototype.hasOwnProperty("popover"),WaPopup=class extends WebAwesomeElement{constructor(){super(...arguments),this.localize=new LocalizeController2(this),this.SUPPORTS_POPOVER=!1,this.active=!1,this.placement="top",this.boundary="viewport",this.distance=0,this.skidding=0,this.arrow=!1,this.arrowPlacement="anchor",this.arrowPadding=10,this.flip=!1,this.flipFallbackPlacements="",this.flipFallbackStrategy="best-fit",this.flipPadding=0,this.shift=!1,this.shiftPadding=0,this.autoSizePadding=0,this.hoverBridge=!1,this.updateHoverBridge=()=>{if(this.hoverBridge&&this.anchorEl&&this.popup){let anchorRect=this.anchorEl.getBoundingClientRect(),popupRect=this.popup.getBoundingClientRect(),isVertical=this.placement.includes("top")||this.placement.includes("bottom"),topLeftX=0,topLeftY=0,topRightX=0,topRightY=0,bottomLeftX=0,bottomLeftY=0,bottomRightX=0,bottomRightY=0;isVertical?anchorRect.top<popupRect.top?(topLeftX=anchorRect.left,topLeftY=anchorRect.bottom,topRightX=anchorRect.right,topRightY=anchorRect.bottom,bottomLeftX=popupRect.left,bottomLeftY=popupRect.top,bottomRightX=popupRect.right,bottomRightY=popupRect.top):(topLeftX=popupRect.left,topLeftY=popupRect.bottom,topRightX=popupRect.right,topRightY=popupRect.bottom,bottomLeftX=anchorRect.left,bottomLeftY=anchorRect.top,bottomRightX=anchorRect.right,bottomRightY=anchorRect.top):anchorRect.left<popupRect.left?(topLeftX=anchorRect.right,topLeftY=anchorRect.top,topRightX=popupRect.left,topRightY=popupRect.top,bottomLeftX=anchorRect.right,bottomLeftY=anchorRect.bottom,bottomRightX=popupRect.left,bottomRightY=popupRect.bottom):(topLeftX=popupRect.right,topLeftY=popupRect.top,topRightX=anchorRect.left,topRightY=anchorRect.top,bottomLeftX=popupRect.right,bottomLeftY=popupRect.bottom,bottomRightX=anchorRect.left,bottomRightY=anchorRect.bottom),this.style.setProperty("--hover-bridge-top-left-x",`${topLeftX}px`),this.style.setProperty("--hover-bridge-top-left-y",`${topLeftY}px`),this.style.setProperty("--hover-bridge-top-right-x",`${topRightX}px`),this.style.setProperty("--hover-bridge-top-right-y",`${topRightY}px`),this.style.setProperty("--hover-bridge-bottom-left-x",`${bottomLeftX}px`),this.style.setProperty("--hover-bridge-bottom-left-y",`${bottomLeftY}px`),this.style.setProperty("--hover-bridge-bottom-right-x",`${bottomRightX}px`),this.style.setProperty("--hover-bridge-bottom-right-y",`${bottomRightY}px`)}}}async connectedCallback(){super.connectedCallback(),await this.updateComplete,this.SUPPORTS_POPOVER=SUPPORTS_POPOVER,this.start()}disconnectedCallback(){super.disconnectedCallback(),this.stop()}async updated(changedProperties){super.updated(changedProperties),changedProperties.has("active")&&(this.active?this.start():this.stop()),changedProperties.has("anchor")&&this.handleAnchorChange(),this.active&&(await this.updateComplete,this.reposition())}async handleAnchorChange(){if(await this.stop(),this.anchor&&typeof this.anchor=="string"){let root=this.getRootNode();this.anchorEl=root.getElementById(this.anchor)}else this.anchor instanceof Element||isVirtualElement(this.anchor)?this.anchorEl=this.anchor:this.anchorEl=this.querySelector('[slot="anchor"]');this.anchorEl instanceof HTMLSlotElement&&(this.anchorEl=this.anchorEl.assignedElements({flatten:!0})[0]),this.anchorEl&&this.start()}start(){!this.anchorEl||!this.active||!this.isConnected||(this.popup?.showPopover?.(),this.cleanup=autoUpdate(this.anchorEl,this.popup,()=>{this.reposition()}))}async stop(){return new Promise(resolve=>{this.popup?.hidePopover?.(),this.cleanup?(this.cleanup(),this.cleanup=void 0,this.removeAttribute("data-current-placement"),this.style.removeProperty("--auto-size-available-width"),this.style.removeProperty("--auto-size-available-height"),requestAnimationFrame(()=>resolve())):resolve()})}reposition(){if(!this.active||!this.anchorEl||!this.popup)return;let middleware=[offset2({mainAxis:this.distance,crossAxis:this.skidding})];this.sync?middleware.push(size2({apply:({rects})=>{let syncWidth=this.sync==="width"||this.sync==="both",syncHeight=this.sync==="height"||this.sync==="both";this.popup.style.width=syncWidth?`${rects.reference.width}px`:"",this.popup.style.height=syncHeight?`${rects.reference.height}px`:""}})):(this.popup.style.width="",this.popup.style.height="");let defaultBoundary;this.SUPPORTS_POPOVER&&!isVirtualElement(this.anchor)&&this.boundary==="scroll"&&(defaultBoundary=getOverflowAncestors(this.anchorEl).filter(el=>el instanceof Element)),this.flip&&middleware.push(flip2({boundary:this.flipBoundary||defaultBoundary,fallbackPlacements:this.flipFallbackPlacements,fallbackStrategy:this.flipFallbackStrategy==="best-fit"?"bestFit":"initialPlacement",padding:this.flipPadding})),this.shift&&middleware.push(shift2({boundary:this.shiftBoundary||defaultBoundary,padding:this.shiftPadding})),this.autoSize?middleware.push(size2({boundary:this.autoSizeBoundary||defaultBoundary,padding:this.autoSizePadding,apply:({availableWidth,availableHeight})=>{this.autoSize==="vertical"||this.autoSize==="both"?this.style.setProperty("--auto-size-available-height",`${availableHeight}px`):this.style.removeProperty("--auto-size-available-height"),this.autoSize==="horizontal"||this.autoSize==="both"?this.style.setProperty("--auto-size-available-width",`${availableWidth}px`):this.style.removeProperty("--auto-size-available-width")}})):(this.style.removeProperty("--auto-size-available-width"),this.style.removeProperty("--auto-size-available-height")),this.arrow&&middleware.push(arrow2({element:this.arrowEl,padding:this.arrowPadding}));let getOffsetParent2=this.SUPPORTS_POPOVER?element=>platform.getOffsetParent(element,e9):platform.getOffsetParent;computePosition2(this.anchorEl,this.popup,{placement:this.placement,middleware,strategy:this.SUPPORTS_POPOVER?"absolute":"fixed",platform:{...platform,getOffsetParent:getOffsetParent2}}).then(({x:x2,y:y3,middlewareData,placement})=>{let isRtl=this.localize.dir()==="rtl",staticSide={top:"bottom",right:"left",bottom:"top",left:"right"}[placement.split("-")[0]];if(this.setAttribute("data-current-placement",placement),Object.assign(this.popup.style,{left:`${x2}px`,top:`${y3}px`}),this.arrow){let arrowX=middlewareData.arrow.x,arrowY=middlewareData.arrow.y,top="",right="",bottom="",left="";if(this.arrowPlacement==="start"){let value=typeof arrowX=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"";top=typeof arrowY=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"",right=isRtl?value:"",left=isRtl?"":value}else if(this.arrowPlacement==="end"){let value=typeof arrowX=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:"";right=isRtl?"":value,left=isRtl?value:"",bottom=typeof arrowY=="number"?`calc(${this.arrowPadding}px - var(--arrow-padding-offset))`:""}else this.arrowPlacement==="center"?(left=typeof arrowX=="number"?"calc(50% - var(--arrow-size-diagonal))":"",top=typeof arrowY=="number"?"calc(50% - var(--arrow-size-diagonal))":""):(left=typeof arrowX=="number"?`${arrowX}px`:"",top=typeof arrowY=="number"?`${arrowY}px`:"");Object.assign(this.arrowEl.style,{top,right,bottom,left,[staticSide]:"calc(var(--arrow-base-offset) - var(--arrow-size-diagonal))"})}}),requestAnimationFrame(()=>this.updateHoverBridge()),this.dispatchEvent(new WaRepositionEvent)}render(){return b2`
      <slot name="anchor" @slotchange=${this.handleAnchorChange}></slot>

      <span
        part="hover-bridge"
        class=${e7({"popup-hover-bridge":!0,"popup-hover-bridge-visible":this.hoverBridge&&this.active})}
      ></span>

      <div
        popover="manual"
        part="popup"
        class=${e7({popup:!0,"popup-active":this.active,"popup-fixed":!this.SUPPORTS_POPOVER,"popup-has-arrow":this.arrow})}
      >
        <slot></slot>
        ${this.arrow?b2`<div part="arrow" class="arrow" role="presentation"></div>`:""}
      </div>
    `}};WaPopup.css=popup_styles_default;__decorateClass([e5(".popup")],WaPopup.prototype,"popup",2);__decorateClass([e5(".arrow")],WaPopup.prototype,"arrowEl",2);__decorateClass([n4({attribute:!1,type:Boolean})],WaPopup.prototype,"SUPPORTS_POPOVER",2);__decorateClass([n4()],WaPopup.prototype,"anchor",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaPopup.prototype,"active",2);__decorateClass([n4({reflect:!0})],WaPopup.prototype,"placement",2);__decorateClass([n4()],WaPopup.prototype,"boundary",2);__decorateClass([n4({type:Number})],WaPopup.prototype,"distance",2);__decorateClass([n4({type:Number})],WaPopup.prototype,"skidding",2);__decorateClass([n4({type:Boolean})],WaPopup.prototype,"arrow",2);__decorateClass([n4({attribute:"arrow-placement"})],WaPopup.prototype,"arrowPlacement",2);__decorateClass([n4({attribute:"arrow-padding",type:Number})],WaPopup.prototype,"arrowPadding",2);__decorateClass([n4({type:Boolean})],WaPopup.prototype,"flip",2);__decorateClass([n4({attribute:"flip-fallback-placements",converter:{fromAttribute:value=>value.split(" ").map(p4=>p4.trim()).filter(p4=>p4!==""),toAttribute:value=>value.join(" ")}})],WaPopup.prototype,"flipFallbackPlacements",2);__decorateClass([n4({attribute:"flip-fallback-strategy"})],WaPopup.prototype,"flipFallbackStrategy",2);__decorateClass([n4({type:Object})],WaPopup.prototype,"flipBoundary",2);__decorateClass([n4({attribute:"flip-padding",type:Number})],WaPopup.prototype,"flipPadding",2);__decorateClass([n4({type:Boolean})],WaPopup.prototype,"shift",2);__decorateClass([n4({type:Object})],WaPopup.prototype,"shiftBoundary",2);__decorateClass([n4({attribute:"shift-padding",type:Number})],WaPopup.prototype,"shiftPadding",2);__decorateClass([n4({attribute:"auto-size"})],WaPopup.prototype,"autoSize",2);__decorateClass([n4()],WaPopup.prototype,"sync",2);__decorateClass([n4({type:Object})],WaPopup.prototype,"autoSizeBoundary",2);__decorateClass([n4({attribute:"auto-size-padding",type:Number})],WaPopup.prototype,"autoSizePadding",2);__decorateClass([n4({attribute:"hover-bridge",type:Boolean})],WaPopup.prototype,"hoverBridge",2);WaPopup=__decorateClass([t3("wa-popup")],WaPopup);var switch_styles_default=i`
  :host {
    --height: var(--wa-form-control-toggle-size);
    --width: calc(var(--height) * 1.75);
    --thumb-size: 0.75em;

    display: inline-flex;
    line-height: var(--wa-form-control-value-line-height);
  }

  label {
    position: relative;
    display: flex;
    align-items: center;
    font: inherit;
    color: var(--wa-form-control-value-color);
    vertical-align: middle;
    cursor: pointer;
  }

  .switch {
    flex: 0 0 auto;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    width: var(--width);
    height: var(--height);
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--height);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    transition-property: translate, background, border-color, box-shadow;
    transition-duration: var(--wa-transition-normal);
    transition-timing-function: var(--wa-transition-easing);
  }

  :host([did-ssr]:not(:defined)) .switch {
    transition-property: unset;
    transition-duration: unset;
    transition-timing-function: unset;
  }

  .switch .thumb {
    aspect-ratio: 1 / 1;
    width: var(--thumb-size);
    height: var(--thumb-size);
    background-color: var(--wa-form-control-border-color);
    border-radius: 50%;
    translate: calc((var(--width) - var(--height)) / -2);
    transition: inherit;
  }
  .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / 2);
  }

  .input {
    position: absolute;
    opacity: 0;
    padding: 0;
    margin: 0;
    pointer-events: none;
  }

  /* Focus */
  label:not(.disabled) .input:focus-visible ~ [part~='control'] {
    outline: var(--wa-focus-ring);
    outline-offset: var(--wa-focus-ring-offset);
  }

  /* Checked */
  .checked .switch {
    background-color: var(--wa-form-control-activated-color);
    border-color: var(--wa-form-control-activated-color);
  }

  .checked .switch .thumb {
    background-color: var(--wa-color-surface-default);
    translate: calc((var(--width) - var(--height)) / 2);
  }
  .checked .switch .thumb:dir(rtl) {
    translate: calc((var(--width) - var(--height)) / -2);
  }

  /* Disabled */
  label:has(> :disabled) {
    opacity: 0.5;
    cursor: not-allowed;
  }

  [part~='label'] {
    display: inline-block;
    line-height: var(--height);
    margin-inline-start: 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  :host([required]) [part~='label']::after {
    content: var(--wa-form-control-required-content);
    color: var(--wa-form-control-required-content-color);
    margin-inline-start: var(--wa-form-control-required-content-offset);
  }

  @media (forced-colors: active) {
    :checked:enabled + .switch:hover .thumb,
    :checked + .switch .thumb {
      background-color: ButtonText;
    }
  }
`;var WaSwitch=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.hasSlotController=new HasSlotController(this,"hint"),this.localize=new LocalizeController2(this),this.title="",this.name=null,this._value=this.getAttribute("value")??null,this.size="m",this.disabled=!1,this._checked=null,this.defaultChecked=this.hasAttribute("checked"),this.required=!1,this.hint="",this.withHint=!1}static get validators(){return[...super.validators,MirrorValidator()]}get value(){return this._value??"on"}set value(val){this._value=val}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}get checked(){return this.valueHasChanged?!!this._checked:this._checked??this.defaultChecked}set checked(val){this._checked=!!val,this.valueHasChanged=!0}handleClick(){this.hasInteracted=!0,this.checked=!this.checked,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0}))})}handleKeyDown(event){let isRtl=this.localize.dir()==="rtl";event.key==="ArrowLeft"&&(event.preventDefault(),this.checked=isRtl,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))})),event.key==="ArrowRight"&&(event.preventDefault(),this.checked=!isRtl,this.updateComplete.then(()=>{this.dispatchEvent(new Event("change",{bubbles:!0,composed:!0})),this.dispatchEvent(new InputEvent("input",{bubbles:!0,composed:!0}))}))}willUpdate(changedProperties){super.willUpdate(changedProperties),(changedProperties.has("value")||changedProperties.has("checked")||changedProperties.has("defaultChecked")||changedProperties.has("disabled"))&&this.handleValueOrCheckedChange()}handleValueOrCheckedChange(){if(this.didSSR&&!this.hasUpdated){this.updateComplete.then(()=>{this.handleValueOrCheckedChange()});return}this.setValue(this.checked?this.value:null,this._value),this.updateValidity()}handleStateChange(){this.hasUpdated&&(this.input.checked=this.checked),this.customStates.set("checked",this.checked),this.updateValidity()}handleDisabledChange(){this.updateValidity()}click(){this.input.click()}focus(options){this.input.focus(options)}blur(){this.input.blur()}setValue(value,stateValue){if(!this.checked){this.internals.setFormValue(null,null);return}this.internals.setFormValue(value??"on",stateValue)}formResetCallback(){this._checked=null,super.formResetCallback(),this.handleValueOrCheckedChange()}render(){let hasHintSlot=this.hasSlotController.test("hint","withHint"),hasHint=this.hint?!0:!!hasHintSlot,checkedAttribute=this.didSSR&&!this.hasUpdated?this.checked:this.defaultChecked,checkedProperty=this.didSSR&&!this.hasUpdated?null:l5(this.checked);return b2`
      <label
        part="base switch"
        class=${e7({checked:this.checked,disabled:this.disabled})}
      >
        <input
          class="input"
          type="checkbox"
          title=${this.title}
          name=${o7(this.name)}
          value=${o7(this.value)}
          .checked=${o7(checkedProperty)}
          ?checked=${checkedAttribute}
          ?disabled=${this.disabled}
          ?required=${this.required}
          role="switch"
          aria-checked=${this.checked?"true":"false"}
          aria-describedby="hint"
          @click=${this.handleClick}
          @keydown=${this.handleKeyDown}
        />

        <span part="control" class="switch">
          <span part="thumb" class="thumb"></span>
        </span>

        <slot part="label" class="label"></slot>
      </label>

      <slot
        id="hint"
        name="hint"
        part="hint"
        class=${e7({"has-slotted":hasHint})}
        aria-hidden=${hasHint?"false":"true"}
        >${this.hint}</slot
      >
    `}};WaSwitch.shadowRootOptions={...WebAwesomeFormAssociatedElement.shadowRootOptions,delegatesFocus:!0};WaSwitch.css=[form_control_styles_default,size_styles_default,switch_styles_default];__decorateClass([e5('input[type="checkbox"]')],WaSwitch.prototype,"input",2);__decorateClass([n4()],WaSwitch.prototype,"title",2);__decorateClass([n4({reflect:!0})],WaSwitch.prototype,"name",2);__decorateClass([n4({reflect:!0})],WaSwitch.prototype,"value",1);__decorateClass([n4({reflect:!0})],WaSwitch.prototype,"size",2);__decorateClass([watch("size")],WaSwitch.prototype,"handleSizeChange",1);__decorateClass([n4({type:Boolean})],WaSwitch.prototype,"disabled",2);__decorateClass([n4({type:Boolean,attribute:!1})],WaSwitch.prototype,"checked",1);__decorateClass([n4({type:Boolean,attribute:"checked",reflect:!0})],WaSwitch.prototype,"defaultChecked",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaSwitch.prototype,"required",2);__decorateClass([n4({attribute:"hint"})],WaSwitch.prototype,"hint",2);__decorateClass([n4({attribute:"with-hint",type:Boolean})],WaSwitch.prototype,"withHint",2);__decorateClass([watch(["checked","defaultChecked"])],WaSwitch.prototype,"handleStateChange",1);__decorateClass([watch("disabled",{waitUntilFirstUpdate:!0})],WaSwitch.prototype,"handleDisabledChange",1);WaSwitch=__decorateClass([t3("wa-switch")],WaSwitch);WaSwitch.disableWarning?.("change-in-update");var tab_styles_default=i`
  :host {
    display: inline-block;
    color: var(--wa-color-neutral-on-quiet);
    font-weight: var(--wa-font-weight-action);
  }

  .tab {
    display: inline-flex;
    align-items: center;
    font: inherit;
    padding: 1em 1.5em;
    white-space: nowrap;
    user-select: none;
    -webkit-user-select: none;
    cursor: pointer;
    transition: color var(--wa-transition-fast) var(--wa-transition-easing);

    ::slotted(wa-icon:first-child) {
      margin-inline-end: 0.5em;
    }

    ::slotted(wa-icon:last-child) {
      margin-inline-start: 0.5em;
    }
  }

  @media (hover: hover) {
    :host(:hover:not([disabled])) .tab {
      color: currentColor;
    }
  }

  :host(:focus) {
    outline: transparent;
  }

  :host(:focus-visible) .tab {
    outline: var(--wa-focus-ring);
    outline-offset: calc(-1 * var(--wa-border-width-l) - var(--wa-focus-ring-offset));
  }

  :host([active]:not([disabled])) {
    color: var(--wa-color-brand-on-quiet);
  }

  :host([disabled]) .tab {
    opacity: 0.5;
    cursor: not-allowed;
  }

  @media (forced-colors: active) {
    :host([active]:not([disabled])) {
      outline: solid 1px transparent;
      outline-offset: -3px;
    }
  }
`;var id=0,WaTab=class extends WebAwesomeElement{constructor(){super(...arguments),this.attrId=++id,this.componentId=`wa-tab-${this.attrId}`,this.panel="",this.active=!1,this.disabled=!1,this.tabIndex=0,this.slot="nav",this.role="tab"}handleActiveChange(){this.setAttribute("aria-selected",this.active?"true":"false")}handleDisabledChange(){this.setAttribute("aria-disabled",this.disabled?"true":"false"),this.disabled&&!this.active?this.tabIndex=-1:this.tabIndex=0}render(){return this.id=this.id?.length>0?this.id:this.componentId,b2`
      <div
        part="base tab"
        class=${e7({tab:!0,"tab-active":this.active})}
      >
        <slot></slot>
      </div>
    `}};WaTab.css=tab_styles_default;__decorateClass([e5(".tab")],WaTab.prototype,"tab",2);__decorateClass([n4({reflect:!0})],WaTab.prototype,"panel",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTab.prototype,"active",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTab.prototype,"disabled",2);__decorateClass([n4({type:Number,reflect:!0})],WaTab.prototype,"tabIndex",2);__decorateClass([n4({reflect:!0})],WaTab.prototype,"slot",2);__decorateClass([n4({reflect:!0})],WaTab.prototype,"role",2);__decorateClass([watch("active")],WaTab.prototype,"handleActiveChange",1);__decorateClass([watch("disabled")],WaTab.prototype,"handleDisabledChange",1);WaTab=__decorateClass([t3("wa-tab")],WaTab);var WaTabShowEvent=class extends Event{constructor(detail){super("wa-tab-show",{bubbles:!0,cancelable:!1,composed:!0}),this.detail=detail}};var WaTabHideEvent=class extends Event{constructor(detail){super("wa-tab-hide",{bubbles:!0,cancelable:!1,composed:!0}),this.detail=detail}};var tab_group_styles_default=i`
  :host {
    --indicator-color: var(--wa-color-brand-fill-loud);
    --track-color: var(--wa-color-neutral-fill-normal);
    --track-width: 0.125rem;

    /* Private */
    --safe-track-width: max(0.5px, round(var(--track-width), 0.5px));

    display: block;
  }

  .tab-group {
    display: flex;
    border-radius: 0;
  }

  .tabs {
    display: flex;
    position: relative;
  }

  .indicator {
    position: absolute;
  }

  .tab-group-has-scroll-controls .nav-container {
    position: relative;
    padding: 0 1.5em;
  }

  .body {
    display: block;
  }

  .scroll-button {
    display: flex;
    align-items: center;
    justify-content: center;
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1.5em;
  }

  .scroll-button-start {
    inset-inline-start: 0;
  }

  .scroll-button-end {
    inset-inline-end: 0;
  }

  /*
    * Top
    */

  .tab-group-top {
    flex-direction: column;
  }

  .tab-group-top .nav-container {
    order: 1;
  }

  .tab-group-top .nav {
    display: flex;
    overflow-x: auto;

    /* Hide scrollbar in Firefox */
    scrollbar-width: none;
  }

  /* Hide scrollbar in Chrome/Safari */
  .tab-group-top .nav::-webkit-scrollbar {
    width: 0;
    height: 0;
  }

  .tab-group-top .tabs {
    flex: 1 1 auto;
    position: relative;
    flex-direction: row;
    border-bottom: solid var(--safe-track-width) var(--track-color);
  }

  .tab-group-top .indicator {
    bottom: calc(-1 * var(--safe-track-width));
    border-bottom: solid var(--safe-track-width) var(--indicator-color);
  }

  .tab-group-top .body {
    order: 2;
  }

  .tab-group-top ::slotted(wa-tab[active]) {
    border-block-end: solid var(--safe-track-width) var(--indicator-color);
    margin-block-end: calc(-1 * var(--safe-track-width));
  }

  .tab-group-top .body slot::slotted(wa-tab-panel) {
    --padding: var(--wa-space-xl) 0;
  }

  /*
    * Bottom
    */

  .tab-group-bottom {
    flex-direction: column;
  }

  .tab-group-bottom .nav-container {
    order: 2;
  }

  .tab-group-bottom .nav {
    display: flex;
    overflow-x: auto;

    /* Hide scrollbar in Firefox */
    scrollbar-width: none;
  }

  /* Hide scrollbar in Chrome/Safari */
  .tab-group-bottom .nav::-webkit-scrollbar {
    width: 0;
    height: 0;
  }

  .tab-group-bottom .tabs {
    flex: 1 1 auto;
    position: relative;
    flex-direction: row;
    border-top: solid var(--safe-track-width) var(--track-color);
  }

  .tab-group-bottom .indicator {
    top: calc(-1 * var(--safe-track-width));
    border-top: solid var(--safe-track-width) var(--indicator-color);
  }

  .tab-group-bottom .body {
    order: 1;
  }

  .tab-group-bottom ::slotted(wa-tab[active]) {
    border-block-start: solid var(--safe-track-width) var(--indicator-color);
    margin-block-start: calc(-1 * var(--safe-track-width));
  }

  .tab-group-bottom .body slot::slotted(wa-tab-panel) {
    --padding: var(--wa-space-xl) 0;
  }

  /*
    * Start
    */

  .tab-group-start {
    flex-direction: row;
  }

  .tab-group-start .nav-container {
    order: 1;
  }

  .tab-group-start .tabs {
    flex: 0 0 auto;
    flex-direction: column;
    border-inline-end: solid var(--safe-track-width) var(--track-color);
  }

  .tab-group-start .indicator {
    inset-inline-end: calc(-1 * var(--safe-track-width));
    border-right: solid var(--safe-track-width) var(--indicator-color);
  }

  .tab-group-start .body {
    flex: 1 1 auto;
    order: 2;
  }

  .tab-group-start ::slotted(wa-tab[active]) {
    border-inline-end: solid var(--safe-track-width) var(--indicator-color);
    margin-inline-end: calc(-1 * var(--safe-track-width));
  }

  .tab-group-start .body slot::slotted(wa-tab-panel) {
    --padding: 0 var(--wa-space-xl);
  }

  /*
    * End
    */

  .tab-group-end {
    flex-direction: row;
  }

  .tab-group-end .nav-container {
    order: 2;
  }

  .tab-group-end .tabs {
    flex: 0 0 auto;
    flex-direction: column;
    border-left: solid var(--safe-track-width) var(--track-color);
  }

  .tab-group-end .indicator {
    inset-inline-start: calc(-1 * var(--safe-track-width));
    border-inline-start: solid var(--safe-track-width) var(--indicator-color);
  }

  .tab-group-end .body {
    flex: 1 1 auto;
    order: 1;
  }

  .tab-group-end ::slotted(wa-tab[active]) {
    border-inline-start: solid var(--safe-track-width) var(--indicator-color);
    margin-inline-start: calc(-1 * var(--safe-track-width));
  }

  .tab-group-end .body slot::slotted(wa-tab-panel) {
    --padding: 0 var(--wa-space-xl);
  }
`;var WaTabGroup=class extends WebAwesomeElement{constructor(){super(...arguments),this.tabs=[],this.focusableTabs=[],this.panels=[],this.localize=new LocalizeController2(this),this.hasScrollControls=!1,this.active="",this.placement="top",this.activation="auto",this.withoutScrollControls=!1}connectedCallback(){super.connectedCallback(),!!1&&(this.resizeObserver=new ResizeObserver(()=>{this.updateScrollControls()}),this.mutationObserver=new MutationObserver(mutations=>{mutations.some(m3=>!["aria-labelledby","aria-controls"].includes(m3.attributeName))&&setTimeout(()=>this.setAriaLabels());let relevantMutations=mutations.filter(m3=>m3.target.closest("wa-tab-group")===this);if(relevantMutations.some(m3=>m3.attributeName==="disabled"))this.syncTabsAndPanels();else if(relevantMutations.some(m3=>m3.attributeName==="active")){let newActiveTab=relevantMutations.filter(m3=>m3.attributeName==="active"&&m3.target.tagName.toLowerCase()==="wa-tab").map(m3=>m3.target).find(tab=>tab.active);newActiveTab&&newActiveTab.closest("wa-tab-group")===this&&this.setActiveTab(newActiveTab)}}),this.updateComplete.then(()=>{this.syncTabsAndPanels(),this.mutationObserver.observe(this,{attributes:!0,childList:!0,subtree:!0}),this.resizeObserver.observe(this.nav),new IntersectionObserver((entries,observer)=>{if(entries[0].intersectionRatio>0){if(this.setAriaLabels(),this.active){let tab=this.tabs.find(t6=>t6.panel===this.active);tab&&this.setActiveTab(tab)}else this.setActiveTab(this.getActiveTab()??this.tabs[0],{emitEvents:!1});observer.unobserve(entries[0].target)}}).observe(this.tabGroup)}))}disconnectedCallback(){super.disconnectedCallback(),this.mutationObserver?.disconnect(),this.nav&&this.resizeObserver?.unobserve(this.nav)}getAllTabs(){return[...this.shadowRoot.querySelector('slot[name="nav"]').assignedElements()].filter(el=>el.tagName.toLowerCase()==="wa-tab")}getAllPanels(){return[...this.defaultSlot.assignedElements()].filter(el=>el.tagName.toLowerCase()==="wa-tab-panel")}getActiveTab(){return this.tabs.find(el=>el.active)}handleClick(event){let tab=event.target.closest("wa-tab");tab?.closest("wa-tab-group")===this&&tab!==null&&this.setActiveTab(tab,{scrollBehavior:"smooth"})}handleKeyDown(event){let tab=event.target.closest("wa-tab");if(tab?.closest("wa-tab-group")===this){if(["Enter"," "].includes(event.key)){tab!==null&&(this.setActiveTab(tab,{scrollBehavior:"smooth"}),event.preventDefault());return}if(["ArrowLeft","ArrowRight","ArrowUp","ArrowDown","Home","End"].includes(event.key)){let activeEl=this.tabs.find(t6=>t6.matches(":focus")),isRtl=this.localize.dir()==="rtl",nextTab=null;if(activeEl?.tagName.toLowerCase()==="wa-tab"){if(event.key==="Home")nextTab=this.focusableTabs[0];else if(event.key==="End")nextTab=this.focusableTabs[this.focusableTabs.length-1];else if(["top","bottom"].includes(this.placement)&&event.key===(isRtl?"ArrowRight":"ArrowLeft")||["start","end"].includes(this.placement)&&event.key==="ArrowUp"){let currentIndex=this.tabs.findIndex(el=>el===activeEl);nextTab=this.findNextFocusableTab(currentIndex,"backward")}else if(["top","bottom"].includes(this.placement)&&event.key===(isRtl?"ArrowLeft":"ArrowRight")||["start","end"].includes(this.placement)&&event.key==="ArrowDown"){let currentIndex=this.tabs.findIndex(el=>el===activeEl);nextTab=this.findNextFocusableTab(currentIndex,"forward")}if(!nextTab)return;nextTab.tabIndex=0,nextTab.focus({preventScroll:!0}),this.activation==="auto"?this.setActiveTab(nextTab,{scrollBehavior:"smooth"}):this.tabs.forEach(tabEl=>{tabEl.tabIndex=tabEl===nextTab?0:-1}),["top","bottom"].includes(this.placement)&&scrollIntoView(nextTab,this.nav,"horizontal"),event.preventDefault()}}}}findNextFocusableTab(currentIndex,direction){let nextTab=null,iterator=direction==="forward"?1:-1,nextIndex=currentIndex+iterator;for(;currentIndex<this.tabs.length;){if(nextTab=this.tabs[nextIndex]||null,nextTab===null){direction==="forward"?nextTab=this.focusableTabs[0]:nextTab=this.focusableTabs[this.focusableTabs.length-1];break}if(!nextTab.disabled)break;nextIndex+=iterator}return nextTab}handleScrollToStart(){this.nav.scroll({left:this.localize.dir()==="rtl"?this.nav.scrollLeft+this.nav.clientWidth:this.nav.scrollLeft-this.nav.clientWidth,behavior:"smooth"})}handleScrollToEnd(){this.nav.scroll({left:this.localize.dir()==="rtl"?this.nav.scrollLeft-this.nav.clientWidth:this.nav.scrollLeft+this.nav.clientWidth,behavior:"smooth"})}setActiveTab(tab,options){if(options={emitEvents:!0,scrollBehavior:"auto",...options},tab.closest("wa-tab-group")===this&&tab!==this.activeTab&&!tab.disabled){let previousTab=this.activeTab;this.active=tab.panel,this.activeTab=tab,this.tabs.forEach(el=>{el.active=el===this.activeTab,el.tabIndex=el===this.activeTab?0:-1}),this.panels.forEach(el=>el.active=el.name===this.activeTab?.panel),["top","bottom"].includes(this.placement)&&scrollIntoView(this.activeTab,this.nav,"horizontal",options.scrollBehavior),options.emitEvents&&(previousTab&&this.dispatchEvent(new WaTabHideEvent({name:previousTab.panel})),this.dispatchEvent(new WaTabShowEvent({name:this.activeTab.panel})))}}setAriaLabels(){this.tabs.forEach(tab=>{let panel=this.panels.find(el=>el.name===tab.panel);panel&&(tab.setAttribute("aria-controls",panel.getAttribute("id")),panel.setAttribute("aria-labelledby",tab.getAttribute("id")))})}syncTabsAndPanels(){this.tabs=this.getAllTabs(),this.focusableTabs=this.tabs.filter(el=>!el.disabled),this.panels=this.getAllPanels(),this.updateComplete.then(()=>this.updateScrollControls())}updateActiveTab(){let tab=this.tabs.find(el=>el.panel===this.active);tab&&this.setActiveTab(tab,{scrollBehavior:"smooth"})}updateScrollControls(){this.withoutScrollControls?this.hasScrollControls=!1:this.hasScrollControls=["top","bottom"].includes(this.placement)&&this.nav.scrollWidth>this.nav.clientWidth+1}render(){let isRtl=this.hasUpdated?this.localize.dir()==="rtl":this.dir==="rtl";return b2`
      <div
        part="base tab-group"
        class=${e7({"tab-group":!0,"tab-group-top":this.placement==="top","tab-group-bottom":this.placement==="bottom","tab-group-start":this.placement==="start","tab-group-end":this.placement==="end","tab-group-has-scroll-controls":this.hasScrollControls})}
        @click=${this.handleClick}
        @keydown=${this.handleKeyDown}
      >
        <div class="nav-container" part="nav">
          ${this.hasScrollControls?b2`
                <wa-button
                  part="scroll-button scroll-button-start"
                  exportparts="base:scroll-button__base"
                  class="scroll-button scroll-button-start"
                  appearance="plain"
                  @click=${this.handleScrollToStart}
                >
                  <wa-icon
                    name=${isRtl?"chevron-right":"chevron-left"}
                    library="system"
                    variant="solid"
                    label=${this.localize.term("scrollToStart")}
                  ></wa-icon>
                </wa-button>
              `:""}

          <!-- We have a focus listener because in Firefox (and soon to be Chrome) overflow containers are focusable. -->
          <div class="nav" @focus=${()=>this.activeTab?.focus({preventScroll:!0})}>
            <div part="tabs" class="tabs" role="tablist">
              <slot name="nav" @slotchange=${this.syncTabsAndPanels}></slot>
            </div>
          </div>

          ${this.hasScrollControls?b2`
                <wa-button
                  part="scroll-button scroll-button-end"
                  class="scroll-button scroll-button-end"
                  exportparts="base:scroll-button__base"
                  appearance="plain"
                  @click=${this.handleScrollToEnd}
                >
                  <wa-icon
                    name=${isRtl?"chevron-left":"chevron-right"}
                    library="system"
                    variant="solid"
                    label=${this.localize.term("scrollToEnd")}
                  ></wa-icon>
                </wa-button>
              `:""}
        </div>

        <div part="body" class="body"><slot @slotchange=${this.syncTabsAndPanels}></slot></div>
      </div>
    `}};WaTabGroup.css=tab_group_styles_default;__decorateClass([e5(".tab-group")],WaTabGroup.prototype,"tabGroup",2);__decorateClass([e5(".body slot")],WaTabGroup.prototype,"defaultSlot",2);__decorateClass([e5(".nav")],WaTabGroup.prototype,"nav",2);__decorateClass([r5()],WaTabGroup.prototype,"hasScrollControls",2);__decorateClass([n4({reflect:!0})],WaTabGroup.prototype,"active",2);__decorateClass([n4()],WaTabGroup.prototype,"placement",2);__decorateClass([n4()],WaTabGroup.prototype,"activation",2);__decorateClass([n4({attribute:"without-scroll-controls",type:Boolean})],WaTabGroup.prototype,"withoutScrollControls",2);__decorateClass([watch("active")],WaTabGroup.prototype,"updateActiveTab",1);__decorateClass([watch("withoutScrollControls",{waitUntilFirstUpdate:!0})],WaTabGroup.prototype,"updateScrollControls",1);WaTabGroup=__decorateClass([t3("wa-tab-group")],WaTabGroup);var tab_panel_styles_default=i`
  :host {
    --padding: 0;

    display: none;
  }

  :host([active]) {
    display: block;
  }

  .tab-panel {
    display: block;
    padding: var(--padding);
  }
`;var id2=0,WaTabPanel=class extends WebAwesomeElement{constructor(){super(...arguments),this.attrId=++id2,this.componentId=`wa-tab-panel-${this.attrId}`,this.name="",this.active=!1,this.role="tabpanel"}connectedCallback(){super.connectedCallback(),this.id=(this.id||"").length>0?this.id:this.componentId}handleActiveChange(){this.setAttribute("aria-hidden",this.active?"false":"true")}render(){return b2`
      <slot
        part="base"
        class=${e7({"tab-panel":!0,"tab-panel-active":this.active})}
      ></slot>
    `}};WaTabPanel.css=tab_panel_styles_default;__decorateClass([n4({reflect:!0})],WaTabPanel.prototype,"name",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTabPanel.prototype,"active",2);__decorateClass([n4({reflect:!0})],WaTabPanel.prototype,"role",2);__decorateClass([watch("active")],WaTabPanel.prototype,"handleActiveChange",1);WaTabPanel=__decorateClass([t3("wa-tab-panel")],WaTabPanel);var textarea_styles_default=i`
  :host {
    border-width: 0;
  }

  .textarea {
    display: grid;
    align-items: center;
    margin: 0;
    border: none;
    outline: none;
    cursor: inherit;
    font: inherit;
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
    border-radius: var(--wa-form-control-border-radius);
    border-style: var(--wa-form-control-border-style);
    border-width: var(--wa-form-control-border-width);
    -webkit-appearance: none;
    outline: var(--wa-focus-ring-style) var(--wa-focus-ring-width) transparent;
    outline-offset: var(--wa-focus-ring-offset);

    &:focus-within {
      outline-color: var(--wa-color-focus);
    }

    /* Style disabled textareas */
    &:has(:disabled) {
      cursor: not-allowed;
      opacity: 0.5;
    }
  }

  /* Appearance modifiers */
  :host([appearance='outlined']) .textarea {
    background-color: var(--wa-form-control-background-color);
    border-color: var(--wa-form-control-border-color);
  }

  :host([appearance='filled']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-color-neutral-fill-quiet);
  }

  :host([appearance='filled-outlined']) .textarea {
    background-color: var(--wa-color-neutral-fill-quiet);
    border-color: var(--wa-form-control-border-color);
  }

  textarea {
    display: block;
    width: 100%;
    border: none;
    background: transparent;
    font: inherit;
    color: inherit;
    cursor: inherit;
    scroll-padding-block: var(--wa-form-control-padding-block);
    padding: calc(var(--wa-form-control-padding-block) - ((1lh - 1em) / 2)) var(--wa-form-control-padding-inline); /* accounts for the larger line height of textarea content */
    min-height: calc(var(--wa-form-control-height) - var(--border-width) * 2);
    box-shadow: none;
    margin: 0;

    &::placeholder {
      color: var(--wa-form-control-placeholder-color);
      user-select: none;
      -webkit-user-select: none;
    }

    &:autofill {
      &,
      &:hover,
      &:focus,
      &:active {
        box-shadow: none;
        caret-color: var(--wa-form-control-value-color);
      }
    }

    &:focus {
      outline: none;
    }
  }

  /* Shared textarea and size-adjuster positioning */
  .control,
  .size-adjuster {
    grid-area: 1 / 1 / 2 / 2;
  }

  .size-adjuster {
    visibility: hidden;
    pointer-events: none;
    opacity: 0;
    padding: 0;
  }

  textarea::-webkit-search-decoration,
  textarea::-webkit-search-cancel-button,
  textarea::-webkit-search-results-button,
  textarea::-webkit-search-results-decoration {
    -webkit-appearance: none;
  }

  /*
   * Resize types
   */

  :host([resize='none']) textarea {
    resize: none;
  }

  textarea,
  :host([resize='vertical']) textarea {
    resize: vertical;
  }

  :host([resize='horizontal']) textarea {
    resize: horizontal;
  }

  :host([resize='both']) textarea {
    resize: both;
  }

  :host([resize='auto']) textarea {
    height: auto;
    resize: none;
    overflow-y: hidden;
  }

  /*
   * Footer (hint + character count)
   */

  /*
   * This element carries the hint part, so the shared form control styles apply to it. Those styles set display:block
   * and hide the element when it has no hint, both of which have to be undone when a character count is present.
   */
  .footer.has-slotted,
  .footer.has-count {
    display: flex;
    align-items: baseline;
    gap: 1em;
  }

  /* Slots default to display:contents, which would leave the hint unable to shrink below its content */
  .footer.has-count .hint {
    display: block;
    flex: 1 1 auto;
    min-width: 0;
  }

  .count {
    flex: 0 0 auto;
    color: var(--wa-form-control-hint-color);
    font-weight: var(--wa-form-control-hint-font-weight);
    line-height: var(--wa-form-control-hint-line-height);
    margin-block-start: 0.5em;
    font-size: var(--wa-font-size-smaller);
    margin-inline-start: auto;
  }
`;var visually_hidden_styles_default=i`
  .wa-visually-hidden:not(:focus-within),
  .wa-visually-hidden-force,
  .wa-visually-hidden-hint::part(hint),
  .wa-visually-hidden-label::part(label),
  .wa-visually-hidden-label::part(form-control-label) {
    top: 0px !important;
    left: 0px !important;
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    clip: rect(0 0 0 0) !important;
    clip-path: inset(50%) !important;
    border: none !important;
    overflow: hidden !important;
    white-space: nowrap !important;
    padding: 0 !important;
  }
`;var WaTextarea=class extends WebAwesomeFormAssociatedElement{constructor(){super(...arguments),this.assumeInteractionOn=["blur","input"],this.hasSlotController=new HasSlotController(this,"hint","label"),this.localize=new LocalizeController2(this),this.announcedCountText="",this.title="",this.name=null,this._value=null,this.defaultValue=this.getAttribute("value")??"",this.size="m",this.appearance="outlined",this.label="",this.hint="",this.placeholder="",this.rows=4,this.resize="vertical",this.disabled=!1,this.readonly=!1,this.required=!1,this.spellcheck=!0,this.withLabel=!1,this.withHint=!1,this.withCount=!1,this.lastObservedWidth=0}static get validators(){return[...super.validators,MirrorValidator()]}get value(){return this.valueHasChanged?this._value:this._value??this.defaultValue}set value(val){this._value!==val&&(this.valueHasChanged=!0,this._value=val)}handleSizeChange(){warnDeprecatedSize(this.localName,this.size)}connectedCallback(){super.connectedCallback(),this.updateComplete.then(()=>{if(this.setTextareaDimensions(),this.updateResizeObserver(),this.didSSR&&this.input&&this.value!==this.input.value){let value=this.input.value;this.value=value}})}disconnectedCallback(){super.disconnectedCallback(),clearTimeout(this.countAnnounceTimeout),this.resizeObserver?.disconnect(),this.resizeObserver=void 0}updateFormValue(value){if(value==null){this.setValue("",null);return}super.updateFormValue(value)}updateResizeObserver(){let needsObserver=this.resize!=="none";this.resizeObserver&&(this.resizeObserver.disconnect(),this.resizeObserver=void 0),needsObserver&&this.input&&(this.resize==="auto"?(this.resizeObserver=new ResizeObserver(entries=>{let width=entries[0]?.contentRect.width??0;width!==this.lastObservedWidth&&(this.lastObservedWidth=width,requestAnimationFrame(()=>this.setTextareaDimensions()))}),this.resizeObserver.observe(this)):(this.resizeObserver=new ResizeObserver(()=>this.setTextareaDimensions()),this.resizeObserver.observe(this.input)))}handleBlur(){this.checkValidity()}handleChange(event){this.valueHasChanged=!0,this.value=this.input.value,this.setTextareaDimensions(),this.checkValidity(),this.relayNativeEvent(event,{bubbles:!0,composed:!0})}handleInput(event){this.valueHasChanged=!0,this.value=this.input.value,this.relayNativeEvent(event,{bubbles:!0,composed:!0}),this.scheduleCountAnnouncement()}scheduleCountAnnouncement(){clearTimeout(this.countAnnounceTimeout),this.countAnnounceTimeout=setTimeout(()=>{let currentLength=(this.value??"").length;this.announcedCountText=this.maxlength!=null?this.localize.term("numCharactersRemaining",this.maxlength-currentLength):this.localize.term("numCharacters",currentLength)},1e3)}setTextareaDimensions(){if(this.resize==="none"){this.base.style.width="",this.base.style.height="";return}if(this.resize==="auto"){this.sizeAdjuster.style.height=`${this.input.clientHeight}px`,this.input.style.height="auto";let newHeight=this.input.scrollHeight;this.input.style.height=`${newHeight}px`,this.sizeAdjuster.style.height=`${newHeight}px`,this.base.style.width="",this.base.style.height="";return}if(this.input.style.width){let width=Number(this.input.style.width.split(/px/)[0])+2;this.base.style.width=`${width}px`}if(this.input.style.height){let height=Number(this.input.style.height.split(/px/)[0])+2;this.base.style.height=`${height}px`}}handleRowsChange(){this.setTextareaDimensions()}async handleValueChange(){await this.updateComplete,this.checkValidity(),this.setTextareaDimensions()}updated(changedProperties){changedProperties.has("resize")&&(this.setTextareaDimensions(),this.updateResizeObserver()),super.updated(changedProperties),changedProperties.has("value")&&this.customStates.set("blank",!this.value)}focus(options){this.input.focus(options)}blur(){this.input.blur()}select(){this.input.select()}scrollPosition(position){if(position){typeof position.top=="number"&&(this.input.scrollTop=position.top),typeof position.left=="number"&&(this.input.scrollLeft=position.left);return}return{top:this.input.scrollTop,left:this.input.scrollTop}}setSelectionRange(selectionStart,selectionEnd,selectionDirection="none"){this.input.setSelectionRange(selectionStart,selectionEnd,selectionDirection)}setRangeText(replacement,start,end,selectMode="preserve"){let selectionStart=start??this.input.selectionStart,selectionEnd=end??this.input.selectionEnd;this.input.setRangeText(replacement,selectionStart,selectionEnd,selectMode),this.value!==this.input.value&&(this.value=this.input.value,this.setTextareaDimensions())}formResetCallback(){this._value=null,this.input&&(this.input.value=this.value||""),super.formResetCallback()}render(){let hasLabelSlot=this.hasSlotController.test("label","withLabel"),hasHintSlot=this.hasSlotController.test("hint","withHint"),hasLabel=this.label?!0:!!hasLabelSlot,hasHint=this.hint?!0:!!hasHintSlot,currentLength=(this.value??"").length,countText=this.maxlength!=null?this.localize.term("numCharactersRemaining",this.maxlength-currentLength):this.localize.term("numCharacters",currentLength);return b2`
      <label
        part="form-control-label label"
        class=${e7({label:!0,"has-label":hasLabel})}
        for="input"
        aria-hidden=${hasLabel?"false":"true"}
      >
        <slot name="label">${this.label}</slot>
      </label>

      <div part="base textarea-wrapper" class="textarea">
        <textarea
          part="textarea"
          id="input"
          class="control"
          title=${this.title}
          name=${o7(this.name)}
          .value=${l5(this.value)}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          ?required=${this.required}
          placeholder=${o7(this.placeholder)}
          rows=${o7(this.rows)}
          minlength=${o7(this.minlength)}
          maxlength=${o7(this.maxlength)}
          autocapitalize=${o7(this.autocapitalize)}
          autocorrect=${o7(this.autocorrect)}
          ?autofocus=${this.autofocus}
          spellcheck=${o7(this.spellcheck)}
          enterkeyhint=${o7(this.enterkeyhint)}
          inputmode=${o7(this.inputmode)}
          aria-describedby="hint"
          @change=${this.handleChange}
          @input=${this.handleInput}
          @blur=${this.handleBlur}
        ></textarea>

        <!-- This "adjuster" exists to prevent layout shifting. https://github.com/shoelace-style/shoelace/issues/2180 -->
        <div part="textarea-adjuster" class="size-adjuster" ?hidden=${this.resize!=="auto"}></div>
      </div>

      <div
        part="hint"
        class=${e7({footer:!0,"has-count":this.withCount,"has-slotted":hasHint})}
      >
        <slot id="hint" name="hint" class="hint" aria-hidden=${hasHint?"false":"true"}>${this.hint}</slot>

        ${this.withCount?b2`
              <div part="count" class="count" aria-hidden="true">${countText}</div>
              <div class="wa-visually-hidden-force" aria-live="polite">${this.announcedCountText}</div>
            `:""}
      </div>
    `}};WaTextarea.css=[textarea_styles_default,form_control_styles_default,size_styles_default,visually_hidden_styles_default];__decorateClass([r5()],WaTextarea.prototype,"announcedCountText",2);__decorateClass([e5(".control")],WaTextarea.prototype,"input",2);__decorateClass([e5('[part~="base"]')],WaTextarea.prototype,"base",2);__decorateClass([e5(".size-adjuster")],WaTextarea.prototype,"sizeAdjuster",2);__decorateClass([n4()],WaTextarea.prototype,"title",2);__decorateClass([n4({reflect:!0})],WaTextarea.prototype,"name",2);__decorateClass([r5()],WaTextarea.prototype,"value",1);__decorateClass([n4({attribute:"value",reflect:!0})],WaTextarea.prototype,"defaultValue",2);__decorateClass([n4({reflect:!0})],WaTextarea.prototype,"size",2);__decorateClass([watch("size")],WaTextarea.prototype,"handleSizeChange",1);__decorateClass([n4({reflect:!0})],WaTextarea.prototype,"appearance",2);__decorateClass([n4()],WaTextarea.prototype,"label",2);__decorateClass([n4({attribute:"hint"})],WaTextarea.prototype,"hint",2);__decorateClass([n4()],WaTextarea.prototype,"placeholder",2);__decorateClass([n4({type:Number})],WaTextarea.prototype,"rows",2);__decorateClass([n4({reflect:!0})],WaTextarea.prototype,"resize",2);__decorateClass([n4({type:Boolean})],WaTextarea.prototype,"disabled",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTextarea.prototype,"readonly",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTextarea.prototype,"required",2);__decorateClass([n4({type:Number})],WaTextarea.prototype,"minlength",2);__decorateClass([n4({type:Number})],WaTextarea.prototype,"maxlength",2);__decorateClass([n4()],WaTextarea.prototype,"autocapitalize",2);__decorateClass([n4({type:Boolean,converter:{fromAttribute:value=>!(!value||value==="off"),toAttribute:value=>value?"on":"off"}})],WaTextarea.prototype,"autocorrect",2);__decorateClass([n4()],WaTextarea.prototype,"autocomplete",2);__decorateClass([n4({type:Boolean})],WaTextarea.prototype,"autofocus",2);__decorateClass([n4()],WaTextarea.prototype,"enterkeyhint",2);__decorateClass([n4({type:Boolean,converter:{fromAttribute:value=>!(!value||value==="false"),toAttribute:value=>value?"true":"false"}})],WaTextarea.prototype,"spellcheck",2);__decorateClass([n4()],WaTextarea.prototype,"inputmode",2);__decorateClass([n4({attribute:"with-label",type:Boolean})],WaTextarea.prototype,"withLabel",2);__decorateClass([n4({attribute:"with-hint",type:Boolean})],WaTextarea.prototype,"withHint",2);__decorateClass([n4({attribute:"with-count",type:Boolean,reflect:!0})],WaTextarea.prototype,"withCount",2);__decorateClass([watch("rows",{waitUntilFirstUpdate:!0})],WaTextarea.prototype,"handleRowsChange",1);__decorateClass([watch("value",{waitUntilFirstUpdate:!0})],WaTextarea.prototype,"handleValueChange",1);WaTextarea=__decorateClass([t3("wa-textarea")],WaTextarea);WaTextarea.disableWarning?.("change-in-update");var tooltip_styles_default=i`
  :host {
    --max-width: 30ch;

    /** These styles are added so we don't interfere in the DOM. */
    display: inline-block;
    position: absolute;

    /** Defaults for inherited CSS properties */
    color: var(--wa-tooltip-content-color);
    font-size: var(--wa-tooltip-font-size);
    line-height: var(--wa-tooltip-line-height);
    text-align: start;
    white-space: normal;
  }

  .tooltip {
    --arrow-size: var(--wa-tooltip-arrow-size);
    --arrow-color: var(--wa-tooltip-background-color);
  }

  .tooltip::part(popup) {
    z-index: 1000;
  }

  .tooltip[placement^='top']::part(popup) {
    transform-origin: bottom;
  }

  .tooltip[placement^='bottom']::part(popup) {
    transform-origin: top;
  }

  .tooltip[placement^='left']::part(popup) {
    transform-origin: right;
  }

  .tooltip[placement^='right']::part(popup) {
    transform-origin: left;
  }

  .body {
    display: block;
    width: max-content;
    max-width: var(--max-width);
    border-radius: var(--wa-tooltip-border-radius);
    background-color: var(--wa-tooltip-background-color);
    border: var(--wa-tooltip-border-width) var(--wa-tooltip-border-style) var(--wa-tooltip-border-color);
    padding: 0.25em 0.5em;
    user-select: none;
    -webkit-user-select: none;
  }

  .tooltip {
    --popup-border-width: var(--wa-tooltip-border-width);

    /* Inset box-shadow, not a border: Safari seams a clip-path edge that runs along a border. */
    &::part(arrow) {
      box-shadow: inset calc(-1 * var(--wa-tooltip-border-width)) calc(-1 * var(--wa-tooltip-border-width)) 0 0
        var(--wa-tooltip-border-color);
    }
  }
`;function containsComposedNode(ancestor,node){for(;node;){if(node===ancestor)return!0;node instanceof Element&&node.assignedSlot?node=node.assignedSlot:node.parentNode?node=node.parentNode:node instanceof ShadowRoot?node=node.host:node=null}return!1}var WaTooltip=class extends WebAwesomeElement{constructor(){super(...arguments),this.dismissedByPress=!1,this.placement="top",this.disabled=!1,this.distance=8,this.open=!1,this.skidding=0,this.showDelay=150,this.hideDelay=0,this.trigger="hover focus",this.withoutArrow=!1,this.for=null,this.anchor=null,this.eventController=new AbortController,this.handleBlur=()=>{this.dismissedByPress=!1,this.hasTrigger("focus")&&this.hide()},this.handleClick=()=>{if(this.hasTrigger("click")){this.open?this.hide():this.show();return}this.hasTrigger("manual")||this.lightDismiss()},this.handleFocus=()=>{this.dismissedByPress||this.hasTrigger("focus")&&this.show()},this.handleMouseDown=()=>{this.hasTrigger("click")||this.hasTrigger("manual")||this.lightDismiss()},this.handleDocumentKeyDown=event=>{this.hasTrigger("manual")||event.key==="Escape"&&this.open&&isTopDismissible(this)&&(event.preventDefault(),event.stopPropagation(),this.hide())},this.handleDocumentClick=event=>{this.hasTrigger("manual")||this.anchor&&event.composedPath().includes(this.anchor)||this.hide()},this.handleMouseOver=()=>{this.dismissedByPress||this.hasTrigger("hover")&&(clearTimeout(this.hoverTimeout),this.hoverTimeout=window.setTimeout(()=>this.show(),this.showDelay))},this.handleMouseOut=event=>{let relatedTarget=event.relatedTarget,movedIntoAnchor=!!(relatedTarget&&this.anchor&&containsComposedNode(this.anchor,relatedTarget)),movedIntoTooltip=!!(relatedTarget&&containsComposedNode(this,relatedTarget));movedIntoAnchor||movedIntoTooltip||(this.dismissedByPress=!1,this.hasTrigger("hover")&&(clearTimeout(this.hoverTimeout),this.hoverTimeout=window.setTimeout(()=>{this.hide()},this.hideDelay)))}}connectedCallback(){super.connectedCallback(),typeof document<"u"&&(this.eventController.signal.aborted&&(this.eventController=new AbortController),this.addEventListener("mouseout",this.handleMouseOut),this.dismissedByPress=!1,this.open&&(this.open=!1,this.updateComplete.then(()=>{this.open=!0})),this.id||(this.id=uniqueId("wa-tooltip-")),this.for&&this.anchor?(this.anchor=null,this.handleForChange()):this.for&&this.handleForChange())}disconnectedCallback(){super.disconnectedCallback(),document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("click",this.handleDocumentClick),unregisterDismissible(this),this.eventController.abort(),this.anchor&&this.removeFromAriaLabelledBy(this.anchor,this.id)}firstUpdated(changedProperties){this.body.hidden=!this.open,this.open&&(this.popup.active=!0,this.popup.reposition()),super.firstUpdated(changedProperties)}lightDismiss(){clearTimeout(this.hoverTimeout),this.dismissedByPress=!0,this.hide()}hasTrigger(triggerType){return this.trigger.split(" ").includes(triggerType)}addToAriaLabelledBy(element,id3){let labels=(element.getAttribute("aria-labelledby")||"").split(/\s+/).filter(Boolean);labels.includes(id3)||(labels.push(id3),element.setAttribute("aria-labelledby",labels.join(" ")))}removeFromAriaLabelledBy(element,id3){let filteredLabels=(element.getAttribute("aria-labelledby")||"").split(/\s+/).filter(Boolean).filter(label=>label!==id3);filteredLabels.length>0?element.setAttribute("aria-labelledby",filteredLabels.join(" ")):element.removeAttribute("aria-labelledby")}async handleOpenChange(){if(this.open){if(this.disabled)return;let waShowEvent=new WaShowEvent;if(this.dispatchEvent(waShowEvent),waShowEvent.defaultPrevented){this.open=!1;return}this.hasTrigger("manual")||(document.addEventListener("keydown",this.handleDocumentKeyDown,{signal:this.eventController.signal}),document.addEventListener("click",this.handleDocumentClick,{signal:this.eventController.signal}),registerDismissible(this)),this.body.hidden=!1,this.popup.active=!0,await animateWithClass(this.popup.popup,"show-with-scale"),this.popup.reposition(),this.dispatchEvent(new WaAfterShowEvent)}else{let waHideEvent=new WaHideEvent;if(this.dispatchEvent(waHideEvent),waHideEvent.defaultPrevented){this.open=!0;return}document.removeEventListener("keydown",this.handleDocumentKeyDown),document.removeEventListener("click",this.handleDocumentClick),unregisterDismissible(this),await animateWithClass(this.popup.popup,"hide-with-scale"),this.popup.active=!1,this.body.hidden=!0,this.dispatchEvent(new WaAfterHideEvent)}}handleForChange(){let rootNode=this.getRootNode?.();if(!rootNode)return;let newAnchor=this.for?rootNode.getElementById?.(this.for):null,oldAnchor=this.anchor;if(newAnchor===oldAnchor)return;this.dismissedByPress=!1;let{signal}=this.eventController;newAnchor&&(this.addToAriaLabelledBy(newAnchor,this.id),newAnchor.addEventListener("blur",this.handleBlur,{capture:!0,signal}),newAnchor.addEventListener("focus",this.handleFocus,{capture:!0,signal}),newAnchor.addEventListener("click",this.handleClick,{signal}),newAnchor.addEventListener("mousedown",this.handleMouseDown,{signal}),newAnchor.addEventListener("mouseover",this.handleMouseOver,{signal}),newAnchor.addEventListener("mouseout",this.handleMouseOut,{signal})),oldAnchor&&(this.removeFromAriaLabelledBy(oldAnchor,this.id),oldAnchor.removeEventListener("blur",this.handleBlur,{capture:!0}),oldAnchor.removeEventListener("focus",this.handleFocus,{capture:!0}),oldAnchor.removeEventListener("click",this.handleClick),oldAnchor.removeEventListener("mousedown",this.handleMouseDown),oldAnchor.removeEventListener("mouseover",this.handleMouseOver),oldAnchor.removeEventListener("mouseout",this.handleMouseOut)),this.anchor=newAnchor}async handleOptionsChange(){this.hasUpdated&&(await this.updateComplete,this.popup.reposition())}handleDisabledChange(){this.disabled&&this.open&&this.hide()}async show(){if(!this.open)return this.open=!0,waitForEvent(this,"wa-after-show")}async hide(){if(this.open)return this.open=!1,waitForEvent(this,"wa-after-hide")}render(){return b2`
      <wa-popup
        part="base tooltip"
        exportparts="
          popup:base__popup,
          arrow:base__arrow
        "
        class=${e7({tooltip:!0,"tooltip-open":this.open})}
        placement=${this.placement}
        distance=${this.distance}
        skidding=${this.skidding}
        flip
        shift
        ?arrow=${!this.withoutArrow}
        hover-bridge
        .anchor=${this.anchor}
      >
        <div part="body" class="body">
          <slot></slot>
        </div>
      </wa-popup>
    `}};WaTooltip.css=tooltip_styles_default;WaTooltip.dependencies={"wa-popup":WaPopup};__decorateClass([e5("slot:not([name])")],WaTooltip.prototype,"defaultSlot",2);__decorateClass([e5(".body")],WaTooltip.prototype,"body",2);__decorateClass([e5("wa-popup")],WaTooltip.prototype,"popup",2);__decorateClass([n4()],WaTooltip.prototype,"placement",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTooltip.prototype,"disabled",2);__decorateClass([n4({type:Number})],WaTooltip.prototype,"distance",2);__decorateClass([n4({type:Boolean,reflect:!0})],WaTooltip.prototype,"open",2);__decorateClass([n4({type:Number})],WaTooltip.prototype,"skidding",2);__decorateClass([n4({attribute:"show-delay",type:Number})],WaTooltip.prototype,"showDelay",2);__decorateClass([n4({attribute:"hide-delay",type:Number})],WaTooltip.prototype,"hideDelay",2);__decorateClass([n4()],WaTooltip.prototype,"trigger",2);__decorateClass([n4({attribute:"without-arrow",type:Boolean,reflect:!0})],WaTooltip.prototype,"withoutArrow",2);__decorateClass([n4()],WaTooltip.prototype,"for",2);__decorateClass([r5()],WaTooltip.prototype,"anchor",2);__decorateClass([watch("open",{waitUntilFirstUpdate:!0})],WaTooltip.prototype,"handleOpenChange",1);__decorateClass([watch("for")],WaTooltip.prototype,"handleForChange",1);__decorateClass([watch(["distance","placement","skidding"])],WaTooltip.prototype,"handleOptionsChange",1);__decorateClass([watch("disabled")],WaTooltip.prototype,"handleDisabledChange",1);WaTooltip=__decorateClass([t3("wa-tooltip")],WaTooltip);registerIconLibrary("default",offlineLibrary);})();
