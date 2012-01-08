<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:db="http://docbook.org/ns/docbook"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="db"
                version="1.0">

<!--!!==========================================================================
DocBook to HTML - Lists
:Requires: db-common db2html-inline db2html-xref gettext html

REMARK: Describe this module
-->


<!-- == Matched Templates == -->

<!-- = glosslist = -->
<xsl:template match="glosslist | db:glosslist">
  <div class="list glosslist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="title | db:title | db:info/db:title"/>
    <dl class="glosslist">
      <xsl:apply-templates select="glossentry | db:glossentry"/>
    </dl>
  </div>
</xsl:template>

<!-- = itemizedlist = -->
<xsl:template match="itemizedlist | db:itemizedlist">
  <div class="list itemizedlist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="db:info/db:title"/>
    <xsl:apply-templates select="*[not(self::listitem) and not(self::db:listitem)]"/>
    <ul>
      <xsl:attribute name="class">
        <xsl:text>list itemizedlist</xsl:text>
        <xsl:if test="@spacing = 'compact'">
          <xsl:text> compact</xsl:text>
        </xsl:if>
      </xsl:attribute>
      <xsl:if test="@mark">
        <xsl:attribute name="style">
          <xsl:text>list-style-type: </xsl:text>
          <xsl:choose>
            <xsl:when test="@mark = 'bullet'">disc</xsl:when>
            <xsl:when test="@mark = 'box'">square</xsl:when>
            <xsl:otherwise><xsl:value-of select="@mark"/></xsl:otherwise>
          </xsl:choose>
        </xsl:attribute>
      </xsl:if>
      <xsl:apply-templates select="listitem | db:listitem"/>
    </ul>
  </div>
</xsl:template>

<!-- = itemizedlist/listitem = -->
<xsl:template match="itemizedlist/listitem | db:itemizedlist/db:listitem">
  <li class="list itemizedlist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:if test="@override">
      <xsl:attribute name="style">
        <xsl:text>list-style-type: </xsl:text>
        <xsl:choose>
          <xsl:when test="@override = 'bullet'">disc</xsl:when>
          <xsl:when test="@override = 'box'">square</xsl:when>
          <xsl:otherwise><xsl:value-of select="@override"/></xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
    </xsl:if>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates/>
  </li>
</xsl:template>

<!-- = member = -->
<xsl:template match="member | db:member">
  <!-- Do something trivial, and rely on simplelist to do the rest -->
  <xsl:call-template name="db2html.inline"/>
</xsl:template>

<!-- = orderedlist = -->
<xsl:template match="orderedlist | db:orderedlist">
  <xsl:variable name="start">
    <xsl:choose>
      <xsl:when test="@continuation = 'continues'">
        <xsl:call-template name="db.orderedlist.start"/>
      </xsl:when>
      <xsl:otherwise>1</xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <!-- FIXME: auto-numeration for nested lists -->
  <div class="list orderedlist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="db:info/db:title"/>
    <xsl:apply-templates select="*[not(self::listitem) and not(self::db:listitem)]"/>
    <ol>
      <xsl:attribute name="class">
        <xsl:text>list orderedlist</xsl:text>
        <xsl:if test="@spacing = 'compact'">
          <xsl:text> compact</xsl:text>
        </xsl:if>
      </xsl:attribute>
      <xsl:if test="@numeration">
        <xsl:attribute name="type">
          <xsl:choose>
            <xsl:when test="@numeration = 'arabic'">1</xsl:when>
            <xsl:when test="@numeration = 'loweralpha'">a</xsl:when>
            <xsl:when test="@numeration = 'lowerroman'">i</xsl:when>
            <xsl:when test="@numeration = 'upperalpha'">A</xsl:when>
            <xsl:when test="@numeration = 'upperroman'">I</xsl:when>
            <xsl:otherwise>1</xsl:otherwise>
          </xsl:choose>
        </xsl:attribute>
      </xsl:if>
      <xsl:if test="$start != '1'">
        <xsl:attribute name="start">
          <xsl:value-of select="$start"/>
        </xsl:attribute>
      </xsl:if>
      <!-- FIXME: @inheritnum -->
      <xsl:apply-templates select="listitem | db:listitem"/>
    </ol>
  </div>
</xsl:template>

<!-- = orderedlist/listitem = -->
<xsl:template match="orderedlist/listitem | db:orderedlist/db:listitem">
  <li class="list orderedlist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:if test="@override">
      <xsl:attribute name="value">
        <xsl:value-of select="@override"/>
      </xsl:attribute>
    </xsl:if>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates/>
  </li>
</xsl:template>

<!-- = procedure = -->
<xsl:template match="procedure | db:procedure">
  <div class="steps">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="db:info/db:title"/>
    <xsl:apply-templates select="*[not(self::step) and not(self::db:step)]"/>
    <xsl:choose>
      <xsl:when test="(count(step) + count(db:step)) = 1">
        <ul class="steps">
          <xsl:apply-templates select="step | db:step"/>
        </ul>
      </xsl:when>
      <xsl:otherwise>
        <ol class="steps">
          <xsl:apply-templates select="step | db:step"/>
        </ol>
      </xsl:otherwise>
    </xsl:choose>
  </div>
</xsl:template>

<!-- = answer = -->
<xsl:template match="answer | db:answer">
  <dd class="answer">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:choose>
      <xsl:when test="label | db:label">
        <div class="qanda-label">
          <xsl:apply-templates select="label/node() | db:label/node()"/>
        </div>
      </xsl:when>
      <xsl:when test="ancestor::qandaset/@defaultlabel = 'qanda' or
                      ancestor::db:qandaset/@defaultlabel = 'qanda'">
        <div class="qanda-label">
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'A:'"/>
          </xsl:call-template>
        </div>
      </xsl:when>
    </xsl:choose>
    <xsl:apply-templates/>
  </dd>
</xsl:template>

<!-- = qandaentry = -->
<xsl:template match="qandaentry | db:qandaentry">
  <xsl:apply-templates/>
</xsl:template>

<!-- = question = -->
<xsl:template match="question | db:question">
  <dt class="question">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:choose>
      <xsl:when test="label | db:label">
        <div class="qanda-label">
          <xsl:apply-templates select="label/node() | db:label/node()"/>
        </div>
      </xsl:when>
      <xsl:when test="ancestor::qandaset/@defaultlabel = 'qanda' or
                      ancestor::db:qandaset/@defaultlabel = 'qanda'">
        <div class="qanda-label">
          <xsl:call-template name="l10n.gettext">
            <xsl:with-param name="msgid" select="'Q:'"/>
          </xsl:call-template>
        </div>
      </xsl:when>
    </xsl:choose>
    <xsl:apply-templates/>
  </dt>
</xsl:template>

<!-- = seg = -->
<xsl:template match="seg | db:seg">
  <xsl:variable name="position"
                select="count(preceding-sibling::seg) +
                        count(preceding-sibling::db:seg) + 1"/>
  <p class="seg">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:apply-templates select="../../segtitle[position() = $position] |
                                 ../../db:segtitle[position() = $position]"/>
    <xsl:apply-templates/>
  </p>
</xsl:template>

<!-- = seglistitem = -->
<xsl:template match="seglistitem | db:seglistitem">
  <xsl:param name="position"
              select="count(preceding-sibling::seglistitem) +
                      count(preceding-sibling::db:seglistitem) + 1"/>
  <div class="seglistitem">
    <xsl:call-template name="html.lang.attrs"/>
    <div>
      <xsl:attribute name="class">
        <xsl:choose>
          <xsl:when test="($position mod 2) = 1">
            <xsl:value-of select="'odd'"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="'even'"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:attribute>
      <xsl:apply-templates/>
    </div>
  </div>
</xsl:template>

<!-- FIXME: Implement tabular segmentedlists -->
<!-- = segmentedlist = -->
<xsl:template match="segmentedlist | db:segmentedlist">
  <div class="list segmentedlist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="title | db:title | db:info/db:title"/>
    <xsl:apply-templates select="seglistitem | db:seglistitem"/>
  </div>
</xsl:template>

<!-- = segtitle = -->
<xsl:template match="segtitle | db:segtitle">
  <!-- FIXME: no style tags -->
  <b>
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:apply-templates/>
    <!-- FIXME: i18n -->
    <xsl:text>: </xsl:text>
  </b>
</xsl:template>

<!-- = simplelist = -->
<xsl:template match="simplelist | db:simplelist">
  <xsl:variable name="columns">
    <xsl:choose>
      <xsl:when test="@columns">
        <xsl:value-of select="@columns"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="1"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:choose>
    <xsl:when test="@type = 'inline'">
      <span class="simplelist">
        <xsl:call-template name="html.lang.attrs"/>
        <xsl:call-template name="db2html.anchor"/>
        <xsl:for-each select="member | db:member">
          <xsl:if test="position() != 1">
            <xsl:call-template name="l10n.gettext">
              <xsl:with-param name="msgid" select="', '"/>
            </xsl:call-template>
          </xsl:if>
          <xsl:apply-templates select="."/>
        </xsl:for-each>
      </span>
    </xsl:when>
    <xsl:when test="@type = 'horiz'">
      <div class="list simplelist">
        <xsl:call-template name="html.lang.attrs"/>
        <xsl:call-template name="db2html.anchor"/>
        <table class="simplelist">
          <xsl:for-each select="(member | db:member)[$columns = 1 or position() mod $columns = 1]">
            <tr>
              <td>
                <xsl:apply-templates select="."/>
              </td>
              <xsl:for-each select="(following-sibling::member |
                                     following-sibling::db:member)[
                                     position() &lt; $columns]">
                <td>
                  <xsl:apply-templates select="."/>
                </td>
              </xsl:for-each>
              <xsl:variable name="fcount" select="count(following-sibling::member) +
                                                  count(following-sibling::db:member)"/>
              <xsl:if test="$fcount &lt; ($columns - 1)">
                <td colspan="{$columns - $fcount - 1}"/>
              </xsl:if>
            </tr>
          </xsl:for-each>
        </table>
      </div>
    </xsl:when>
    <xsl:otherwise>
      <div class="list simplelist">
        <xsl:call-template name="html.lang.attrs"/>
        <xsl:call-template name="db2html.anchor"/>
        <xsl:variable name="rows"
                      select="ceiling(count(member | db:member) div $columns)"/>
        <table class="simplelist">
          <xsl:for-each select="(member | db:member)[position() &lt;= $rows]">
            <tr>
              <td>
                <xsl:apply-templates select="."/>
              </td>
              <xsl:for-each select="(following-sibling::member |
                                    following-sibling::db:member)[
                                    position() mod $rows = 0]">
                <td>
                  <xsl:apply-templates select="."/>
                </td>
              </xsl:for-each>
              <xsl:if test="position() = $rows">
                <xsl:variable name="fcount"
                              select="count((following-sibling::member | following-sibling::db:member)[position() mod $rows = 0])"/>
                <xsl:if test="$fcount &lt; ($columns - 1)">
                  <td colspan="{$columns - $fcount - 1}"/>
                </xsl:if>
              </xsl:if>
            </tr>
          </xsl:for-each>
        </table>
      </div>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<!-- FIXME: Do something with @performance -->
<!-- = step = -->
<xsl:template match="step | db:step">
  <li class="steps">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:apply-templates/>
  </li>
</xsl:template>

<!-- FIXME: Do something with @performance -->
<!-- = substeps = -->
<xsl:template match="substeps | db:substeps">
  <xsl:variable name="depth" select="count(ancestor::substeps |
                                           ancestor::db:substeps)"/>
  <div class="steps substeps">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <ol class="steps substeps">
      <xsl:attribute name="type">
        <xsl:choose>
          <xsl:when test="$depth mod 3 = 0">a</xsl:when>
          <xsl:when test="$depth mod 3 = 1">i</xsl:when>
          <xsl:when test="$depth mod 3 = 2">1</xsl:when>
        </xsl:choose>
      </xsl:attribute>
      <xsl:apply-templates/>
    </ol>
  </div>
</xsl:template>

<!-- = term = -->
<xsl:template match="term | db:term">
  <dt class="terms">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:if test="(../varlistentry/@id and not(preceding-sibling::term)) or
                  (../db:varlistentry/@xml:id and not(preceding-sibling::db:term))">
      <xsl:call-template name="db2html.anchor">
        <xsl:with-param name="node" select=".."/>
      </xsl:call-template>
    </xsl:if>
    <xsl:apply-templates select="db:info/db:title"/>
    <xsl:apply-templates/>
  </dt>
</xsl:template>

<!-- = variablelist = -->
<xsl:template match="variablelist | db:variablelist">
  <div class="terms variablelist">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates select="db:info/db:title"/>
    <xsl:apply-templates select="*[not(self::varlistentry) and
                                   not(self::db:varlistentry)]"/>
    <dl class="terms variablelist">
      <xsl:apply-templates select="varlistentry |db:varlistentry"/>
    </dl>
  </div>
</xsl:template>

<!-- = varlistentry = -->
<xsl:template match="varlistentry | db:varlistentry">
  <xsl:apply-templates select="term | db:term"/>
  <xsl:apply-templates select="listitem | db:listitem"/>
</xsl:template>

<!-- = varlistentry/listitem = -->
<xsl:template match="varlistentry/listitem | db:varlistentry/db:listitem">
  <dd class="terms">
    <xsl:call-template name="html.lang.attrs"/>
    <xsl:call-template name="db2html.anchor"/>
    <xsl:apply-templates/>
  </dd>
</xsl:template>

</xsl:stylesheet>
