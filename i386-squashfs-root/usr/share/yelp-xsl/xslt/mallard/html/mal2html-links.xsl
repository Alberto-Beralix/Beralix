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
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:ui="http://projectmallard.org/experimental/ui/"
                xmlns:e="http://projectmallard.org/experimental/"
                xmlns:api="http://projectmallard.org/experimental/api/"
                xmlns:exsl="http://exslt.org/common"
                xmlns:math="http://exslt.org/math"
                xmlns:html="http://www.w3.org/1999/xhtml"
                xmlns="http://www.w3.org/1999/xhtml"
                exclude-result-prefixes="mal e api exsl math html"
                version="1.0">

<!--!!==========================================================================
Mallard to HTML - Links

This stylesheet contains templates to handle automatic linking, both using the
Mallard links element and implicitly.
-->


<!--**==========================================================================
mal2html.links.ul
Output links in an HTML #{ul} element.
:Revision:version="1.0" date="2011-06-15" status="final"
$links: A list of #{links}, as from a template in !{mal-link}.
$role: A link role, used to select the appropriate title.
$bold: Whether to bold the link titles.
$nodesc: Whether to omit descriptions.

This is a common formatting template used by some #{links} element handlers.
It outputs an HTML #{ul} element and calls *{mal2html.links.ul.li} on each
link to output a list item with a link.

This template will handle sorting of the links.
-->
<xsl:template name="mal2html.links.ul">
  <xsl:param name="links" select="/false"/>
  <xsl:param name="role" select="''"/>
  <xsl:param name="bold" select="false()"/>
  <xsl:param name="nodesc" select="false()"/>
  <ul>
    <xsl:for-each select="$links">
      <xsl:sort data-type="number" select="@groupsort"/>
      <xsl:sort select="mal:title[@type = 'sort']"/>
      <xsl:call-template name="mal2html.links.ul.li">
        <xsl:with-param name="role" select="$role"/>
        <xsl:with-param name="bold" select="$bold"/>
        <xsl:with-param name="nodesc" select="$nodesc"/>
      </xsl:call-template>
    </xsl:for-each>
  </ul>
</xsl:template>


<!--**==========================================================================
mal2html.links.ul.li
Output a list item with a link.
:Revision:version="1.0" date="2011-06-15" status="final"
$xref: An #{xref} string pointing to the target node.
$role: A link role, used to select the appropriate title.
$bold: Whether to bold the link titles.
$nodesc: Whether to omit descriptions.

This template is called by *{mal2html.links.ul} to output a list item with
a link for each target.
-->
<xsl:template name="mal2html.links.ul.li">
  <xsl:param name="xref" select="@xref"/>
  <xsl:param name="role" select="''"/>
  <xsl:param name="bold" select="false()"/>
  <xsl:param name="nodesc" select="false()"/>
  <xsl:for-each select="$mal.cache">
    <xsl:variable name="target" select="key('mal.cache.key', $xref)"/>
    <li class="links">
      <a>
        <xsl:if test="$bold">
          <xsl:attribute name="class">
            <xsl:text>bold</xsl:text>
          </xsl:attribute>
        </xsl:if>
        <xsl:attribute name="href">
          <xsl:call-template name="mal.link.target">
            <xsl:with-param name="xref" select="$xref"/>
          </xsl:call-template>
        </xsl:attribute>
        <xsl:attribute name="title">
          <xsl:call-template name="mal.link.tooltip">
            <xsl:with-param name="xref" select="$xref"/>
          </xsl:call-template>
        </xsl:attribute>
        <xsl:call-template name="mal.link.content">
          <xsl:with-param name="node" select="."/>
          <xsl:with-param name="xref" select="$xref"/>
          <xsl:with-param name="role" select="$role"/>
        </xsl:call-template>
      </a>
      <xsl:call-template name="mal2html.editor.badge">
        <xsl:with-param name="target" select="$target"/>
      </xsl:call-template>
      <xsl:if test="not($nodesc)">
        <xsl:variable name="desc" select="$target/mal:info/mal:desc"/>
        <xsl:if test="$desc">
          <span class="desc">
            <xsl:text> &#x2014; </xsl:text>
            <xsl:apply-templates mode="mal2html.inline.mode" select="$desc/node()"/>
          </span>
        </xsl:if>
      </xsl:if>
    </li>
  </xsl:for-each>
</xsl:template>


<!--**==========================================================================
mal2html.links.guide
Output guide links from a page or section.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: A #{links}, #{page}, or #{section} element to link from.
$depth: The depth level for the HTML header element.
$links: A list of links from *{mal.link.guidelinks}.

This template outputs guide links for a page or section. It does not extract
the links itself. They must be passed in with the ${links} parameter.
-->
<xsl:template name="mal2html.links.guide" match="mal:links[@type = 'guide']">
  <xsl:param name="node" select="."/>
  <xsl:param name="depth" select="count($node/ancestor-or-self::mal:section) + 2"/>
  <xsl:param name="links" select="/false"/>
  <xsl:variable name="depth_">
    <xsl:choose>
      <xsl:when test="$depth &lt; 6">
        <xsl:value-of select="$depth"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="6"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:variable name="expander" select="$node/self::mal:links/@ui:expanded"/>
  <xsl:if test="$links">
    <div>
      <xsl:attribute name="class">
        <xsl:text>links guidelinks</xsl:text>
        <xsl:if test="$expander">
          <xsl:text> ui-expander</xsl:text>
        </xsl:if>
      </xsl:attribute>
      <xsl:call-template name="mal2html.ui.expander.data">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="expander" select="$expander"/>
      </xsl:call-template>
      <div class="inner">
        <xsl:choose>
          <xsl:when test="$node[self::mal:links]/mal:title">
            <xsl:apply-templates mode="mal2html.block.mode" select="$node/mal:title">
              <xsl:with-param name="depth" select="$depth"/>
            </xsl:apply-templates>
          </xsl:when>
          <xsl:otherwise>
            <div class="title">
              <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
                <span class="title">
                  <xsl:call-template name="l10n.gettext">
                    <xsl:with-param name="msgid" select="'More About'"/>
                  </xsl:call-template>
                </span>
              </xsl:element>
            </div>
          </xsl:otherwise>
        </xsl:choose>
        <div class="region">
          <xsl:call-template name="mal2html.links.ul">
            <xsl:with-param name="links" select="$links"/>
            <xsl:with-param name="role" select="'guide'"/>
          </xsl:call-template>
        </div>
      </div>
    </div>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
mal2html.links.next
Output links to the previous and next pages.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: A #{links} or #{page} element to link from.

This template outputs links to the previous and next page in a Mallard series,
if they exist. The block containing the links is end-floated by default. The
links use the text "Previous" and "Next", although the actual page titles are
used for tooltips.

If the #{links} element has the style hint #{top}, it will be inserted before
the page title, instead of in its position on the page. This is handled by the
calling functions in !{mal2html-page}.
-->
<xsl:template name="mal2html.links.next" match="mal:links[@type = 'next']">
  <xsl:param name="node" select="."/>
  <xsl:variable name="page" select="$node/ancestor-or-self::mal:page[last()]"/>
  <xsl:variable name="linkid">
    <xsl:call-template name="mal.link.linkid">
      <xsl:with-param name="node" select="$page"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="next" select="$page/mal:info/mal:link[@type='next']"/>
  <xsl:for-each select="$mal.cache">
    <xsl:variable name="prev" select="key('mal.cache.link.key', concat('next:', $linkid))"/>
    <xsl:if test="$prev or $next">
      <!-- FIXME: Get prev/next links in constant position -->
      <div class="links nextlinks">
        <xsl:if test="$prev">
          <a class="nextlinks-prev">
            <xsl:attribute name="href">
              <xsl:call-template name="mal.link.target">
                <xsl:with-param name="node" select="$prev"/>
                <xsl:with-param name="xref" select="$prev/../../@id"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:attribute name="title">
              <xsl:call-template name="mal.link.tooltip">
                <xsl:with-param name="node" select="$prev"/>
                <xsl:with-param name="xref" select="$prev/../../@id"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:for-each select="$page">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Previous'"/>
              </xsl:call-template>
            </xsl:for-each>
          </a>
        </xsl:if>
        <xsl:if test="$prev and $next">
          <xsl:text>&#x00A0;&#x00A0;|&#x00A0;&#x00A0;</xsl:text>
        </xsl:if>
        <xsl:if test="$next">
          <a class="nextlinks-next">
            <xsl:attribute name="href">
              <xsl:call-template name="mal.link.target">
                <xsl:with-param name="node" select="$next"/>
                <xsl:with-param name="xref" select="$next/@xref"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:attribute name="title">
              <xsl:call-template name="mal.link.tooltip">
                <xsl:with-param name="node" select="$next"/>
                <xsl:with-param name="xref" select="$next/@xref"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:for-each select="$page">
              <xsl:call-template name="l10n.gettext">
                <xsl:with-param name="msgid" select="'Next'"/>
              </xsl:call-template>
            </xsl:for-each>
          </a>
        </xsl:if>
      </div>
    </xsl:if>
  </xsl:for-each>
</xsl:template>


<!--**==========================================================================
mal2html.links.section
Output links to subsections.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: The section #{links} element.
$depth: The depth level for the HTML header element.

This template outputs links to the child sections of the #{page} or #{section}
element containing ${node}.
-->
<xsl:template name="mal2html.links.section" match="mal:links[@type = 'section']">
  <xsl:param name="node" select="."/>
  <xsl:param name="depth" select="count($node/ancestor-or-self::mal:section) + 2"/>
  <xsl:variable name="style" select="concat(' ', $node/@style, ' ')"/>
  <xsl:if test="$node/../mal:section">
    <div>
      <xsl:attribute name="class">
        <xsl:text>links sectionlinks</xsl:text>
        <xsl:choose>
          <xsl:when test="contains($style, ' floatstart ')">
            <xsl:text> floatstart</xsl:text>
          </xsl:when>
          <xsl:when test="contains($style, ' floatend ')">
            <xsl:text> floatend</xsl:text>
          </xsl:when>
          <xsl:when test="contains($style, ' floatleft ')">
            <xsl:text> floatleft</xsl:text>
          </xsl:when>
          <xsl:when test="contains($style, ' floatright ')">
            <xsl:text> floatright</xsl:text>
          </xsl:when>
        </xsl:choose>
        <xsl:if test="mal:title and $node/@ui:expanded">
          <xsl:text> ui-expander</xsl:text>
        </xsl:if>
      </xsl:attribute>
      <xsl:call-template name="mal2html.ui.expander.data">
        <xsl:with-param name="node" select="$node"/>
      </xsl:call-template>
      <div class="inner">
        <xsl:apply-templates mode="mal2html.block.mode" select="$node/mal:title">
          <xsl:with-param name="depth" select="$depth"/>
        </xsl:apply-templates>
        <div class="region">
          <ul>
            <xsl:for-each select="$node/../mal:section">
              <xsl:call-template name="mal2html.links.ul.li">
                <xsl:with-param name="xref" select="concat(/mal:page/@id, '#', @id)"/>
                <xsl:with-param name="role" select="'section'"/>
              </xsl:call-template>
            </xsl:for-each>
          </ul>
        </div>
      </div>
    </div>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
mal2html.links.seealso
Output seealso links from a page or section.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: A #{links}, #{page}, or #{section} element to link from.
$depth: The depth level for the HTML header element.
$links: A list of links from *{mal.link.seealsolinks}.

This template outputs seealso links for a page or section. It does not extract
the links itself. They must be passed in with the ${links} parameter.
-->
<xsl:template name="mal2html.links.seealso" match="mal:links[@type = 'seealso']">
  <xsl:param name="node" select="."/>
  <xsl:param name="depth" select="count($node/ancestor-or-self::mal:section) + 2"/>
  <xsl:param name="links" select="/false"/>
  <xsl:variable name="depth_">
    <xsl:choose>
      <xsl:when test="$depth &lt; 6">
        <xsl:value-of select="$depth"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="6"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:variable name="expander" select="$node/self::mal:links/@ui:expanded"/>
  <xsl:if test="$links">
    <div>
      <xsl:attribute name="class">
        <xsl:text>links seealsolinks</xsl:text>
        <xsl:if test="$expander">
          <xsl:text> ui-expander</xsl:text>
        </xsl:if>
      </xsl:attribute>
      <xsl:call-template name="mal2html.ui.expander.data">
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="expander" select="$expander"/>
      </xsl:call-template>
      <div class="inner">
        <xsl:choose>
          <xsl:when test="$node[self::mal:links]/mal:title">
            <xsl:apply-templates mode="mal2html.block.mode" select="$node/mal:title">
              <xsl:with-param name="depth" select="$depth"/>
            </xsl:apply-templates>
          </xsl:when>
          <xsl:otherwise>
            <div class="title">
              <xsl:element name="{concat('h', $depth_)}" namespace="{$html.namespace}">
                <span class="title">
                  <xsl:call-template name="l10n.gettext">
                    <xsl:with-param name="msgid" select="'See Also'"/>
                  </xsl:call-template>
                </span>
              </xsl:element>
            </div>
          </xsl:otherwise>
        </xsl:choose>
        <div class="region">
          <xsl:call-template name="mal2html.links.ul">
            <xsl:with-param name="links" select="$links"/>
            <xsl:with-param name="role" select="'seealso'"/>
          </xsl:call-template>
        </div>
      </div>
    </div>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
mal2html.links.series
Output links to pages in a series.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: A #{links} or #{page} element to start from.

A series in Mallard is a list of page such that each page in the list has a
next link to the following page. This template outputs links to each page in
a series. The current page is output in its place, althought it is not a link.

This template calls *{mal2html.links.series.prev} and
*{mal2html.links.series.next} to find and output the links.
-->
<xsl:template name="mal2html.links.series" match="mal:links[@type = 'series']">
  <xsl:param name="node" select="."/>
  <xsl:variable name="page" select="$node/ancestor-or-self::mal:page[last()]"/>
  <xsl:variable name="title" select="$node/self::mal:links/mal:title"/>
  <xsl:variable name="style" select="concat(' ', $node/@style, ' ')"/>
  <xsl:variable name="expander" select="$title and $node/self::mal:links/@ui:expanded"/>
  <div>
    <xsl:attribute name="class">
      <xsl:text>links serieslinks</xsl:text>
      <xsl:choose>
        <xsl:when test="contains($style, ' floatstart ')">
          <xsl:text> floatstart</xsl:text>
        </xsl:when>
        <xsl:when test="contains($style, ' floatend ')">
          <xsl:text> floatend</xsl:text>
        </xsl:when>
        <xsl:when test="contains($style, ' floatleft ')">
          <xsl:text> floatleft</xsl:text>
        </xsl:when>
        <xsl:when test="contains($style, ' floatright ')">
          <xsl:text> floatright</xsl:text>
        </xsl:when>
      </xsl:choose>
      <xsl:if test="$expander">
        <xsl:text> ui-expander</xsl:text>
      </xsl:if>
    </xsl:attribute>
    <xsl:call-template name="mal2html.ui.expander.data">
      <xsl:with-param name="node" select="$node"/>
      <xsl:with-param name="expander" select="$expander"/>
    </xsl:call-template>
    <div class="inner">
      <xsl:apply-templates mode="mal2html.block.mode" select="$title"/>
      <div class="region">
        <ul>
          <xsl:call-template name="mal2html.links.series.prev">
            <xsl:with-param name="node" select="$page"/>
          </xsl:call-template>
          <li class="links">
            <xsl:call-template name="mal.link.content">
              <xsl:with-param name="node" select="$page"/>
              <xsl:with-param name="xref" select="$page/@id"/>
            </xsl:call-template>
          </li>
          <xsl:call-template name="mal2html.links.series.next">
            <xsl:with-param name="node" select="$page"/>
          </xsl:call-template>
        </ul>
      </div>
    </div>
  </div>
</xsl:template>


<!--**==========================================================================
mal2html.links.series.prev
Output preceding links to pages in a series.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: The current #{page} element.

This template is called by *{mal2html.links.series} to output the pages before
the starting page in the series. This template finds the previous page for the
page ${node}. It then calls itself recursively on that page, and outputs a link
to it.
-->
<xsl:template name="mal2html.links.series.prev">
  <xsl:param name="node"/>
  <xsl:variable name="linkid">
    <xsl:call-template name="mal.link.linkid">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:for-each select="$mal.cache">
    <xsl:variable name="prev" select="key('mal.cache.link.key', concat('next:', $linkid))"/>
    <xsl:if test="$prev">
      <xsl:call-template name="mal2html.links.series.prev">
        <xsl:with-param name="node" select="key('mal.cache.key', $prev/../../@id)"/>
      </xsl:call-template>
      <li class="links">
        <a>
          <xsl:attribute name="href">
            <xsl:call-template name="mal.link.target">
              <xsl:with-param name="node" select="$prev"/>
              <xsl:with-param name="xref" select="$prev/../../@id"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:attribute name="title">
            <xsl:call-template name="mal.link.tooltip">
              <xsl:with-param name="node" select="$prev"/>
              <xsl:with-param name="xref" select="$prev/../../@id"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:call-template name="mal.link.content">
            <xsl:with-param name="node" select="$prev"/>
            <xsl:with-param name="xref" select="$prev/../../@id"/>
          </xsl:call-template>
        </a>
      </li>
    </xsl:if>
  </xsl:for-each>
</xsl:template>


<!--**==========================================================================
mal2html.links.series.next
Output following links to pages in a series.
:Revision:version="1.0" date="2011-06-15" status="final"
$node: The current #{page} element.

This template is called by *{mal2html.links.series} to output the pages after
the starting page in the series. This template finds the next page for the page
${node}. It outputs a link to that page, then calls itself recursively on that
page.
-->
<xsl:template name="mal2html.links.series.next">
  <xsl:param name="node"/>
  <xsl:variable name="linkid">
    <xsl:call-template name="mal.link.linkid">
      <xsl:with-param name="node" select="$node"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="next" select="$node/mal:info/mal:link[@type='next']"/>
  <xsl:if test="$next">
    <xsl:for-each select="$mal.cache">
      <li class="links">
        <a>
          <xsl:attribute name="href">
            <xsl:call-template name="mal.link.target">
              <xsl:with-param name="node" select="$next"/>
              <xsl:with-param name="xref" select="$next/@xref"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:attribute name="title">
            <xsl:call-template name="mal.link.tooltip">
              <xsl:with-param name="node" select="$next"/>
              <xsl:with-param name="xref" select="$next/@xref"/>
            </xsl:call-template>
          </xsl:attribute>
          <xsl:call-template name="mal.link.content">
            <xsl:with-param name="node" select="$next"/>
            <xsl:with-param name="xref" select="$next/@xref"/>
          </xsl:call-template>
        </a>
      </li>
      <xsl:call-template name="mal2html.links.series.next">
        <xsl:with-param name="node" select="key('mal.cache.key', $next/@xref)"/>
      </xsl:call-template>
    </xsl:for-each>
  </xsl:if>
</xsl:template>


<!--**==========================================================================
mal2html.links.topic
Output topic links from a page or section.
:Revision:version="1.0" date="2011-06-16" status="final"
$node: A #{links}, #{page}, or #{section} element to link from.
$depth: The depth level for the HTML header element.
$links: A list of links from *{mal.link.topiclinks}.
$groups: The list of link groups for this #{links} element.
$allgroups: The list of all valid groups for the page or section.

This template outputs topic links for a page or section. It does not extract
the links itself. They must be passed in with the ${links} parameter. This
template only outputs links which have a group that matches ${groups}. The
${groups} parameter is not expected to have the implicit groups #{first},
#{default}, and #{last}. These are added automatically by this template
when determining which links to output.
-->
<xsl:template name="mal2html.links.topic" match="mal:links[@type = 'topic']">
  <xsl:param name="node" select="."/>
  <xsl:param name="depth" select="count($node/ancestor-or-self::mal:section) + 2"/>
  <xsl:param name="links" select="/false"/>
  <xsl:param name="groups">
    <xsl:text> </xsl:text>
    <xsl:choose>
      <xsl:when test="$node/@groups">
        <xsl:value-of select="$node/@groups"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:text>#default</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
    <xsl:text> </xsl:text>
  </xsl:param>
  <xsl:param name="allgroups" select="''"/>
  <xsl:variable name="title" select="$node/self::mal:links/mal:title"/>
  <xsl:variable name="expander" select="$title and $node/self::mal:links/@ui:expanded"/>
  <xsl:if test="$node/ancestor-or-self::mal:page[last()]/@type = 'guide'">
    <xsl:variable name="_groups">
      <xsl:if test="not(contains($allgroups, ' #first '))">
        <xsl:if test="not($node/self::mal:links) or not($node/preceding-sibling::mal:links[@type = 'topic'])">
          <xsl:text> #first </xsl:text>
        </xsl:if>
      </xsl:if>
      <xsl:value-of select="$groups"/>
      <xsl:if test="not(contains($allgroups, ' #default '))">
        <xsl:if test="not($node/self::mal:links) or not($node/following-sibling::mal:links[@type = 'topic'])">
          <xsl:text> #default </xsl:text>
        </xsl:if>
      </xsl:if>
      <xsl:if test="not(contains($allgroups, ' #last '))">
        <xsl:if test="not($node/self::mal:links) or not($node/following-sibling::mal:links[@type = 'topic'])">
          <xsl:text> #last </xsl:text>
        </xsl:if>
      </xsl:if>
    </xsl:variable>
    <xsl:variable name="_links" select="$links[contains($_groups, concat(' ', @group, ' '))]"/>
    <xsl:variable name="style" select="concat(' ', $node/@style, ' ')"/>
    <xsl:variable name="nodesc" select="contains($style, ' nodesc ')"/>
    <xsl:if test="count($_links) != 0">
      <div>
        <xsl:attribute name="class">
          <xsl:text>links topiclinks</xsl:text>
          <xsl:if test="$expander">
            <xsl:text> ui-expander</xsl:text>
          </xsl:if>
        </xsl:attribute>
        <xsl:call-template name="mal2html.ui.expander.data">
          <xsl:with-param name="node" select="$node"/>
          <xsl:with-param name="expander" select="$expander"/>
        </xsl:call-template>
        <div class="inner">
          <xsl:if test="$node/self::mal:links">
            <xsl:apply-templates mode="mal2html.block.mode" select="$node/mal:title">
              <xsl:with-param name="depth" select="$depth"/>
            </xsl:apply-templates>
          </xsl:if>
          <div class="region">
            <xsl:choose>
              <xsl:when test="$node/self::mal:links/@api:type='function'">
                <xsl:call-template name="mal2html.api.links.function">
                  <xsl:with-param name="node" select="$node"/>
                  <xsl:with-param name="links" select="$_links"/>
                </xsl:call-template>
              </xsl:when>
              <xsl:when test="contains($style, ' mouseovers ')">
                <xsl:call-template name="_mal2html.links.mouseovers">
                  <xsl:with-param name="node" select="$node"/>
                  <xsl:with-param name="links" select="$_links"/>
                </xsl:call-template>
              </xsl:when>
              <xsl:when test="contains($style, ' toronto ')">
                <xsl:call-template name="_mal2html.links.grid">
                  <xsl:with-param name="node" select="$node"/>
                  <xsl:with-param name="links" select="$_links"/>
                </xsl:call-template>
              </xsl:when>
              <xsl:when test="contains($style, ' linklist ')">
                <xsl:variable name="bold" select="contains($style, ' bold ')"/>
                <xsl:call-template name="mal2html.links.ul">
                  <xsl:with-param name="links" select="$_links"/>
                  <xsl:with-param name="role" select="'topic'"/>
                  <xsl:with-param name="bold" select="$bold"/>
                  <xsl:with-param name="nodesc" select="$nodesc"/>
                </xsl:call-template>
              </xsl:when>
              <xsl:when test="contains($style, ' 2column ')">
                <xsl:variable name="coltot" select="ceiling(count($_links) div 2)"/>
                <table class="twocolumn"><tr>
                  <td class="twocolumnleft">
                    <xsl:call-template name="_mal2html.links.divs">
                      <xsl:with-param name="node" select="$node"/>
                      <xsl:with-param name="links" select="$_links"/>
                      <xsl:with-param name="nodesc" select="$nodesc"/>
                      <xsl:with-param name="max" select="$coltot"/>
                    </xsl:call-template>
                  </td>
                  <td class="twocolumnright">
                    <xsl:call-template name="_mal2html.links.divs">
                      <xsl:with-param name="node" select="$node"/>
                      <xsl:with-param name="links" select="$_links"/>
                      <xsl:with-param name="nodesc" select="$nodesc"/>
                      <xsl:with-param name="min" select="$coltot"/>
                    </xsl:call-template>
                  </td>
                </tr></table>
              </xsl:when>
              <xsl:otherwise>
                <xsl:call-template name="_mal2html.links.divs">
                  <xsl:with-param name="node" select="$node"/>
                  <xsl:with-param name="links" select="$_links"/>
                  <xsl:with-param name="nodesc" select="$nodesc"/>
                </xsl:call-template>
              </xsl:otherwise>
            </xsl:choose>
          </div>
        </div>
      </div>
    </xsl:if>
  </xsl:if>
</xsl:template>

<xsl:template name="_mal2html.links.mouseovers">
  <xsl:param name="node"/>
  <xsl:param name="links"/>
  <div class="mouseovers">
    <xsl:for-each select="$node/e:mouseover[not(@match)]">
      <img>
        <xsl:copy-of select="@src | @width | @height"/>
      </img>
    </xsl:for-each>
  </div>
  <ul class="mouseovers">
    <xsl:for-each select="$links">
      <xsl:sort data-type="number" select="@groupsort"/>
      <xsl:sort select="mal:title[@type = 'sort']"/>
      <xsl:variable name="xref" select="@xref"/>
      <xsl:for-each select="$mal.cache">
        <xsl:variable name="target" select="key('mal.cache.key', $xref)"/>
        <li class="links">
          <a class="bold">
            <xsl:attribute name="href">
              <xsl:call-template name="mal.link.target">
                <xsl:with-param name="xref" select="$xref"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:attribute name="title">
              <xsl:call-template name="mal.link.tooltip">
                <xsl:with-param name="xref" select="$xref"/>
              </xsl:call-template>
            </xsl:attribute>
            <xsl:for-each select="$node/e:mouseover[@match = $xref]">
              <img>
                <xsl:copy-of select="@src | @width | @height"/>
              </img>
            </xsl:for-each>
            <xsl:call-template name="mal.link.content">
              <xsl:with-param name="node" select="."/>
              <xsl:with-param name="xref" select="$xref"/>
              <xsl:with-param name="role" select="'topic'"/>
            </xsl:call-template>
          </a>
        </li>
      </xsl:for-each>
    </xsl:for-each>
  </ul>
</xsl:template>

<xsl:template name="_mal2html.links.grid">
  <xsl:param name="node"/>
  <xsl:param name="links"/>
  <xsl:variable name="rows" select="ceiling(count($links) div 3)"/>
  <table class="toronto">
    <xsl:for-each select="$links[position() &lt;= $rows]">
      <xsl:variable name="rownum" select="position() - 1"/>
      <tr>
        <xsl:for-each select="$links">
          <xsl:sort data-type="number" select="@groupsort"/>
          <xsl:sort select="mal:title[@type = 'sort']"/>
          <xsl:if test="(position() - 1 &gt;= (3 * $rownum)) and
                        (position() - 1 &lt; (3 * $rownum) + 3)">
            <xsl:variable name="xref" select="@xref"/>
            <td>
              <xsl:for-each select="$mal.cache">
                <xsl:variable name="target" select="key('mal.cache.key', $xref)"/>
                <div class="toronto-link"><a>
                  <xsl:attribute name="href">
                    <xsl:call-template name="mal.link.target">
                      <xsl:with-param name="xref" select="$xref"/>
                    </xsl:call-template>
                  </xsl:attribute>
                  <xsl:attribute name="title">
                    <xsl:call-template name="mal.link.tooltip">
                      <xsl:with-param name="xref" select="$xref"/>
                    </xsl:call-template>
                  </xsl:attribute>
                  <xsl:call-template name="mal.link.content">
                    <xsl:with-param name="node" select="."/>
                    <xsl:with-param name="xref" select="$xref"/>
                    <xsl:with-param name="role" select="'topic'"/>
                  </xsl:call-template>
                </a></div>
                <xsl:variable name="desc" select="$target/mal:info/mal:desc"/>
                <xsl:if test="$desc">
                  <div class="toronto-desc desc">
                    <span class="desc">
                      <xsl:apply-templates mode="mal2html.inline.mode" select="$desc/node()"/>
                    </span>
                  </div>
                </xsl:if>
              </xsl:for-each>
            </td>
          </xsl:if>
        </xsl:for-each>
      </tr>
    </xsl:for-each>
  </table>
</xsl:template>

<xsl:template name="_mal2html.links.divs">
  <xsl:param name="node"/>
  <xsl:param name="links"/>
  <xsl:param name="nodesc" select="false()"/>
  <xsl:param name="min" select="-1"/>
  <xsl:param name="max" select="-1"/>
  <xsl:for-each select="$links">
    <xsl:sort data-type="number" select="@groupsort"/>
    <xsl:sort select="mal:title[@type = 'sort']"/>
    <xsl:variable name="xref" select="@xref"/>
    <xsl:if test="($max = -1 or position() &lt;= $max) and
                  ($min = -1 or position() &gt; $min)">
      <xsl:for-each select="$mal.cache">
        <xsl:call-template name="_mal2html.links.divs.link">
          <xsl:with-param name="source" select="$node"/>
          <xsl:with-param name="target" select="key('mal.cache.key', $xref)"/>
          <xsl:with-param name="role" select="'topic'"/>
          <xsl:with-param name="nodesc" select="$nodesc"/>
        </xsl:call-template>
      </xsl:for-each>
    </xsl:if>
  </xsl:for-each>
</xsl:template>

<xsl:template name="_mal2html.links.divs.link">
  <xsl:param name="source" select="."/>
  <xsl:param name="target"/>
  <xsl:param name="class" select="''"/>
  <xsl:param name="attrs"/>
  <xsl:param name="role" select="''"/>
  <xsl:param name="nodesc" select="false()"/>
  <a class="{concat($class, ' linkdiv')}">
    <xsl:attribute name="href">
      <xsl:call-template name="mal.link.target">
        <xsl:with-param name="node" select="$source"/>
        <xsl:with-param name="xref" select="$target/@id"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:attribute name="title">
      <xsl:call-template name="mal.link.tooltip">
        <xsl:with-param name="node" select="$source"/>
        <xsl:with-param name="xref" select="$target/@id"/>
      </xsl:call-template>
    </xsl:attribute>
    <xsl:copy-of select="exsl:node-set($attrs)/*/@*"/>
    <span class="title">
      <xsl:call-template name="mal.link.content">
        <xsl:with-param name="node" select="$source"/>
        <xsl:with-param name="xref" select="$target/@id"/>
        <xsl:with-param name="role" select="$role"/>
      </xsl:call-template>
      <xsl:call-template name="mal2html.editor.badge">
        <xsl:with-param name="target" select="$target"/>
      </xsl:call-template>
    </span>
    <xsl:if test="not($nodesc) and $target/mal:info/mal:desc">
      <span class="linkdiv-dash">
        <xsl:text> &#x2014; </xsl:text>
      </span>
      <span class="desc">
        <xsl:apply-templates mode="mal2html.inline.mode"
                             select="$target/mal:info/mal:desc[1]/node()"/>
      </span>
    </xsl:if>
  </a>
</xsl:template>

</xsl:stylesheet>
