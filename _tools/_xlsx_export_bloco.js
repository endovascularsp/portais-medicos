/* ══ XLSX-EXPORT-BLOCO-INICIO (v1 — 27/07/2026) ══════════════════
   Exporta os honorários do período como planilha Excel (.xlsx) real:
   tabela plana, uma linha por atendimento, no mesmo layout de colunas
   da Base Compensação. Gerador de xlsx embutido (sem biblioteca externa).
   Colunas ausentes no PDATA (Nº OS, Solicitante, Indicação, NF,
   Data compensação) saem vazias até o gerador mensal passar a gravá-las.
   ═════════════════════════════════════════════════════════════════ */

const _XLSX_COLS = [
  {h:'Empresa',           t:'s', w:16, get:(a,d)=>d.empresa},
  {h:'Mês',               t:'s', w:11, get:(a,d)=>a._mes||d.mes},
  {h:'Ano',               t:'i', w:7,  get:(a,d)=>a._ano||d.ano},
  {h:'Nº OS',             t:'i', w:11, get:a=>a['Nº OS']},
  {h:'Profissional',      t:'s', w:26, get:(a,d)=>d.profissional},
  {h:'Solicitante',       t:'s', w:26, get:a=>a['Solicitante']},
  {h:'Paciente',          t:'s', w:30, get:a=>a['Paciente']},
  {h:'Indicação',         t:'s', w:22, get:a=>a['Indicação']},
  {h:'Tabela',            t:'s', w:16, get:a=>a['Tabela']},
  {h:'Procedimento',      t:'s', w:40, get:a=>a['Procedimento']},
  {h:'Categoria',         t:'s', w:20, get:a=>a['Categoria']},
  // O campo sempre trouxe a CONTA de recebimento ("SP Itau - Endovascular"),
  // nunca o número da nota. Rótulo corrigido em 13/08/2026, a pedido do Thiago;
  // o campo do PDATA continua 'NF' para não obrigar a republicar mês nenhum.
  {h:'Conta',             t:'s', w:24, get:a=>a['NF']},
  {h:'Data emissão',      t:'d', w:14, get:a=>a['Data emissão']||a['Data agendamento']},
  {h:'Data compensação',  t:'d', w:17, get:a=>a['Data compensação']},
  {h:'Tipo de pagamento', t:'s', w:20, get:a=>a['Tipo de pagamento']},
  {h:'Valor recebido',    t:'m', w:15, get:a=>a['Valor recebido']},
  {h:'Imposto (18%)',     t:'m', w:15, get:a=>a['Imposto (18%)']},
  {h:'Taxa cartão (3%)',  t:'m', w:15, get:a=>a['Taxa cartão (3%)']},
  {h:'Custo',             t:'m', w:13, get:a=>a['Custo']},
  {h:'Valor Líquido',     t:'m', w:15, get:a=>a['Valor Líquido']},
  {h:'% Profissional',    t:'m', w:15, get:a=>a['Repasse Profissional (R$)']},
  // A parte da clínica não vai no arquivo do médico (pedido do Dr. Igor,
  // 14/08/2026). O número continua na aba "Base de dados" do card de
  // Fechamento, que é interna — lá a lista de colunas é outra, lida do banco.
  // Tirada dos 35 portais por `_tirar_clinica_do_medico.py`.
];

function _xmlEsc(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function _colLetra(n){let s='';while(n>0){const r=(n-1)%26;s=String.fromCharCode(65+r)+s;n=(n-r-1)/26;}return s;}

// 'dd/mm/aaaa' -> número de série do Excel (base 1899-12-30)
function _dataSerial(v){
  const m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(String(v||'').trim());
  if(!m) return null;
  return Math.round((Date.UTC(+m[3],+m[2]-1,+m[1])-Date.UTC(1899,11,30))/86400000);
}

let _CRC_TAB=null;
function _crc32(buf){
  if(!_CRC_TAB){
    _CRC_TAB=new Uint32Array(256);
    for(let i=0;i<256;i++){let c=i;for(let k=0;k<8;k++)c=(c&1)?(0xEDB88320^(c>>>1)):(c>>>1);_CRC_TAB[i]=c>>>0;}
  }
  let c=0xFFFFFFFF;
  for(let i=0;i<buf.length;i++)c=_CRC_TAB[(c^buf[i])&0xFF]^(c>>>8);
  return (c^0xFFFFFFFF)>>>0;
}

// ZIP sem compressão (método "stored") — suficiente e sem dependências
function _zipStore(arquivos){
  const enc=new TextEncoder(), locais=[], central=[]; let off=0;
  arquivos.forEach(f=>{
    const nome=enc.encode(f.nome), crc=_crc32(f.dados), n=f.dados.length;
    const lh=new Uint8Array(30+nome.length), dv=new DataView(lh.buffer);
    dv.setUint32(0,0x04034b50,true); dv.setUint16(4,20,true); dv.setUint16(6,0x0800,true);
    dv.setUint32(14,crc,true); dv.setUint32(18,n,true); dv.setUint32(22,n,true);
    dv.setUint16(26,nome.length,true);
    lh.set(nome,30); locais.push(lh,f.dados);
    const ch=new Uint8Array(46+nome.length), dc=new DataView(ch.buffer);
    dc.setUint32(0,0x02014b50,true); dc.setUint16(4,20,true); dc.setUint16(6,20,true);
    dc.setUint16(8,0x0800,true);
    dc.setUint32(16,crc,true); dc.setUint32(20,n,true); dc.setUint32(24,n,true);
    dc.setUint16(28,nome.length,true); dc.setUint32(42,off,true);
    ch.set(nome,46); central.push(ch);
    off+=lh.length+n;
  });
  const cdSize=central.reduce((s,c)=>s+c.length,0);
  const eocd=new Uint8Array(22), de=new DataView(eocd.buffer);
  de.setUint32(0,0x06054b50,true);
  de.setUint16(8,arquivos.length,true); de.setUint16(10,arquivos.length,true);
  de.setUint32(12,cdSize,true); de.setUint32(16,off,true);
  const partes=locais.concat(central,[eocd]);
  const out=new Uint8Array(partes.reduce((s,p)=>s+p.length,0));
  let p=0; partes.forEach(x=>{out.set(x,p);p+=x.length;});
  return out;
}

const _FMT_BRL='_-&quot;R$&quot;\\ * #,##0.00_-;\\-&quot;R$&quot;\\ * #,##0.00_-;_-&quot;R$&quot;\\ * &quot;-&quot;??_-;_-@_-';

function _xlsxEstilos(){
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
  '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+
  '<numFmts count="2"><numFmt numFmtId="164" formatCode="'+_FMT_BRL+'"/>'+
  '<numFmt numFmtId="165" formatCode="dd/mm/yyyy"/></numFmts>'+
  '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'+
  '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'+
  '<fills count="3"><fill><patternFill patternType="none"/></fill>'+
  '<fill><patternFill patternType="gray125"/></fill>'+
  '<fill><patternFill patternType="solid"><fgColor rgb="FF1F3864"/><bgColor indexed="64"/></patternFill></fill></fills>'+
  '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'+
  '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'+
  '<cellXfs count="4">'+
  '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'+
  '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1">'+
  '<alignment horizontal="center" vertical="center" wrapText="1"/></xf>'+
  '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'+
  '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'+
  '</cellXfs>'+
  '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'+
  '</styleSheet>';
}

function _xlsxPlanilha(cols,linhas){
  const larguras='<cols>'+cols.map((c,i)=>
    '<col min="'+(i+1)+'" max="'+(i+1)+'" width="'+c.w+'" customWidth="1"/>').join('')+'</cols>';
  let sd='<sheetData><row r="1" ht="26" customHeight="1">'+cols.map((c,i)=>
    '<c r="'+_colLetra(i+1)+'1" s="1" t="inlineStr"><is><t xml:space="preserve">'+_xmlEsc(c.h)+'</t></is></c>').join('')+'</row>';
  linhas.forEach((vals,ri)=>{
    const r=ri+2; let cells='';
    vals.forEach((v,ci)=>{
      if(v===null||v===undefined||v==='') return;
      const ref=_colLetra(ci+1)+r, tipo=cols[ci].t;
      if(tipo==='m')      cells+='<c r="'+ref+'" s="2"><v>'+(+v||0)+'</v></c>';
      else if(tipo==='d'){
        const s=_dataSerial(v);
        cells+= (s!==null) ? '<c r="'+ref+'" s="3"><v>'+s+'</v></c>'
                           : '<c r="'+ref+'" t="inlineStr"><is><t>'+_xmlEsc(v)+'</t></is></c>';
      }
      else if(tipo==='i'&&!isNaN(+v)) cells+='<c r="'+ref+'"><v>'+(+v)+'</v></c>';
      else cells+='<c r="'+ref+'" t="inlineStr"><is><t xml:space="preserve">'+_xmlEsc(v)+'</t></is></c>';
    });
    sd+='<row r="'+r+'">'+cells+'</row>';
  });
  sd+='</sheetData>';
  const ref='A1:'+_colLetra(cols.length)+(linhas.length+1);
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
  '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'+
  '<dimension ref="'+ref+'"/>'+
  '<sheetViews><sheetView workbookViewId="0">'+
  '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'+
  '<sheetFormatPr defaultRowHeight="15"/>'+larguras+sd+
  '<autoFilter ref="'+ref+'"/></worksheet>';
}

function _xlsxArquivo(nomeAba,cols,linhas){
  const enc=new TextEncoder(), b=s=>enc.encode(s);
  const REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships';
  return _zipStore([
    {nome:'[Content_Types].xml', dados:b('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
      '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'+
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'+
      '<Default Extension="xml" ContentType="application/xml"/>'+
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+
      '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'+
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+
      '</Types>')},
    {nome:'_rels/.rels', dados:b('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+
      '<Relationship Id="rId1" Type="'+REL+'/officeDocument" Target="xl/workbook.xml"/></Relationships>')},
    {nome:'xl/workbook.xml', dados:b('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
      '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="'+REL+'">'+
      '<sheets><sheet name="'+_xmlEsc(nomeAba).slice(0,31)+'" sheetId="1" r:id="rId1"/></sheets></workbook>')},
    {nome:'xl/_rels/workbook.xml.rels', dados:b('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+
      '<Relationship Id="rId1" Type="'+REL+'/worksheet" Target="worksheets/sheet1.xml"/>'+
      '<Relationship Id="rId2" Type="'+REL+'/styles" Target="styles.xml"/></Relationships>')},
    {nome:'xl/styles.xml', dados:b(_xlsxEstilos())},
    {nome:'xl/worksheets/sheet1.xml', dados:b(_xlsxPlanilha(cols,linhas))},
  ]);
}

function exportarCSVProf(){
  const d=DADOS_PROFS[PROF_ATUAL]; if(!d) return;
  const ats=d.atendimentos||[];
  if(!ats.length){ showToast('Nenhum atendimento no período.'); return; }
  const linhas=ats.map(a=>_XLSX_COLS.map(c=>{ try{ return c.get(a,d); }catch(e){ return ''; } }));
  const periodo=((typeof PERIODO_LABEL!=='undefined'&&PERIODO_LABEL)?PERIODO_LABEL:((d.mes||'')+'/'+(d.ano||'')))
    .replace(/\s*→\s*/g,' a ').replace(/\//g,'.').replace(/[\\:*?"<>|]/g,'').trim();
  _downloadBin(_xlsxArquivo('Honorários',_XLSX_COLS,linhas),
               'Honorários - '+d.profissional+' - '+periodo+'.xlsx');
  showToast('Planilha exportada!');
}

function _downloadBin(bytes,nome){
  const blob=new Blob([bytes],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download=nome;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1500);
}
/* ══ XLSX-EXPORT-BLOCO-FIM ═══════════════════════════════════════ */
